"""Plano de apostas in-play com oportunidades ranqueadas e regras de blindagem."""
from __future__ import annotations

from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot
from models.ev_value import evaluate_outcome
from models.wc_bet_advice import (
    UserBetInput,
    _market_odd,
    _prob_from_inplay,
    advise_aportes,
    advise_cashout,
    scan_all_market_edges,
)

_CORRELATION_GROUPS: list[frozenset[str]] = [
    frozenset({"h2h:1", "next_goal:home"}),
    frozenset({"h2h:2", "next_goal:away"}),
    frozenset({"over_2_5:yes", "btts:yes"}),
    frozenset({"over_2_5:yes", "over_3_5:yes"}),
]


def _market_key(market: str, outcome: str) -> str:
    return f"{market}:{outcome.lower()}"


def _tier(ev: float, threshold: float) -> str:
    if ev >= threshold * 2.5:
        return "forte"
    if ev >= threshold * 1.5:
        return "moderada"
    if ev >= threshold:
        return "leve"
    return "abaixo_limiar"


def _time_decay_confidence(minute: int) -> float:
    """P1.2: Reduz confiança na reta final — exige edge maior para apostar.

    Lógica: no final do jogo a variância é altíssima (qualquer evento decide).
    Aplicamos um multiplicador < 1.0 que, ao dividir o threshold, o AUMENTA.
    Exemplo: threshold 4%, minuto 82 → effective = 4% / 0.65 = 6.15%
    """
    if minute >= 85:
        return 0.55  # Últimos 5 min: muito conservador
    if minute >= 80:
        return 0.65  # Últimos 10 min: conservador
    if minute >= 75:
        return 0.80  # Últimos 15 min: cauteloso
    if minute >= 70:
        return 0.90  # Após 70': leve cautela
    return 1.0  # Antes de 70': confiança plena


def _posture(
    *,
    cashout_action: str | None,
    strong_ops: int,
    minute: int,
    remaining_ev: float | None,
) -> str:
    if cashout_action in {"cashout", "cashout_parcial"}:
        return "defensivo"
    if minute >= 85:
        return "defensivo"
    if remaining_ev is not None and remaining_ev < -0.06:
        return "defensivo"
    if strong_ops >= 2 and minute < 70:
        return "atacar"
    if strong_ops >= 1:
        return "neutro"
    return "neutro"


def _correlation_warnings(opportunities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shields: list[dict[str, Any]] = []
    keys = {_market_key(o["market"], o["outcome"]) for o in opportunities}
    for group in _CORRELATION_GROUPS:
        overlap = [k for k in keys if k in group]
        if len(overlap) >= 2:
            labels = [o["label"] for o in opportunities if _market_key(o["market"], o["outcome"]) in overlap]
            shields.append({
                "action": "reduzir_exposicao",
                "priority": "alta",
                "title": "Apostas correlacionadas",
                "reason": (
                    f"Mercados ligados no mesmo cenário: {', '.join(labels)}. "
                    "Reduza stake combinada em 50% ou escolha só o de maior EV."
                ),
            })
    return shields


def _house_trap_shields(benchmark: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not benchmark:
        return []
    shields: list[dict[str, Any]] = []
    label_map = {"1": "Casa (1)", "X": "Empate (X)", "2": "Fora (2)"}
    for key, row in (benchmark.get("h2h") or {}).items():
        edge = float(row.get("edge") or 0)
        if edge < -0.05:
            shields.append({
                "action": "evitar",
                "priority": "media",
                "title": f"Evitar {label_map.get(key, key)}",
                "reason": (
                    f"A casa precifica {label_map.get(key, key)} acima do modelo "
                    f"({edge * 100:.1f} pp). Não é lado para aporte."
                ),
            })
    return shields


def _hedge_suggestions(
    user_bet: UserBetInput | None,
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    threshold: float,
    minute: int = 0,
) -> list[dict[str, Any]]:
    if user_bet is None or snapshot is None:
        return []
    shields: list[dict[str, Any]] = []
    cashout = advise_cashout(user_bet, inplay, minute=minute)
    if cashout.action in {"cashout", "cashout_parcial"}:
        return shields

    hedge_specs: list[tuple[str, str, str]] = []
    if user_bet.market == "h2h" and user_bet.outcome == "1":
        hedge_specs = [("h2h", "X", "Empate"), ("h2h", "2", "Fora vence")]
    elif user_bet.market == "h2h" and user_bet.outcome == "2":
        hedge_specs = [("h2h", "X", "Empate"), ("h2h", "1", "Casa vence")]
    elif user_bet.market == "h2h" and user_bet.outcome.upper() in {"X", "0"}:
        hedge_specs = [("h2h", "1", "Casa vence"), ("h2h", "2", "Fora vence")]

    for market, outcome, label in hedge_specs:
        prob = _prob_from_inplay(inplay, market, outcome)
        odd = _market_odd(snapshot, market, outcome)
        if prob is None or odd is None or odd <= 1.0:
            continue
        ev = evaluate_outcome(outcome, prob, odd)
        if ev.expected_value < threshold:
            continue
        shields.append({
            "action": "hedge_opcional",
            "priority": "baixa",
            "title": f"Hedge: {label}",
            "reason": (
                f"Proteção parcial da aposta aberta. {label} com EV +{ev.expected_value * 100:.1f}% "
                f"(stake sugerida ≤ 30% da aposta original)."
            ),
            "market": market,
            "outcome": outcome,
            "odd": round(odd, 2),
            "expected_value": round(ev.expected_value, 4),
        })
    return shields


def build_bet_strategy_report(
    *,
    home_team: str,
    away_team: str,
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    benchmark: dict[str, Any] | None,
    user_bet: UserBetInput | None = None,
    minute: int = 0,
    bankroll: float = 1000.0,
    h2h_overround: float | None = None,
) -> dict[str, Any]:
    all_edges, threshold = scan_all_market_edges(
        inplay,
        snapshot,
        bankroll=bankroll,
        live=True,
        home_team=home_team,
        away_team=away_team,
    )
    aportes = advise_aportes(
        inplay,
        snapshot,
        bankroll=bankroll,
        max_recommendations=8,
        live=True,
        home_team=home_team,
        away_team=away_team,
    )

    cashout = None
    remaining_ev = None
    if user_bet is not None:
        cashout_advice = advise_cashout(user_bet, inplay, minute=minute)
        remaining_ev = cashout_advice.remaining_ev
        cashout = {
            "action": cashout_advice.action,
            "confidence": cashout_advice.confidence,
            "reason": cashout_advice.reason,
        }

    opportunities: list[dict[str, Any]] = []
    # P1.2: threshold efetivo aumenta na reta final (time decay de confiança)
    decay = _time_decay_confidence(minute)
    effective_threshold = threshold / decay if decay > 0 else threshold
    for rank, a in enumerate(aportes, start=1):
        tier = _tier(a.expected_value, effective_threshold)
        stake_pct = a.suggested_stake_pct
        if tier == "leve":
            stake_pct = round(min(stake_pct, 1.5), 2)
        # Na reta final, reduzir stakes adicionalmente
        if minute >= 80:
            stake_pct = round(stake_pct * 0.6, 2)
        elif minute >= 75:
            stake_pct = round(stake_pct * 0.8, 2)
        opportunities.append({
            "rank": rank,
            "market": a.market,
            "outcome": a.outcome,
            "label": a.label,
            "tier": tier,
            "model_prob": a.model_prob,
            "market_odd": a.market_odd,
            "expected_value": a.expected_value,
            "edge_pp": a.edge_pp,
            "suggested_stake_pct": stake_pct,
            "suggested_stake_value": round(bankroll * stake_pct / 100, 2),
            "action": a.action,
        })

    strong_ops = sum(1 for o in opportunities if o["tier"] in {"forte", "moderada"})
    posture = _posture(
        cashout_action=cashout["action"] if cashout else None,
        strong_ops=strong_ops,
        minute=minute,
        remaining_ev=remaining_ev,
    )

    total_exposure_pct = round(sum(o["suggested_stake_pct"] for o in opportunities[:3]), 2)
    max_new_exposure_pct = min(5.0, total_exposure_pct) if posture != "defensivo" else min(2.0, total_exposure_pct)

    shields: list[dict[str, Any]] = []

    if posture == "defensivo":
        shields.append({
            "action": "proteger_banca",
            "priority": "alta",
            "title": "Modo defensivo",
            "reason": (
                "Priorize cash-out ou aguarde. Novos aportes limitados a no máximo "
                f"{max_new_exposure_pct:.1f}% da banca."
            ),
        })

    if minute >= 75:
        shields.append({
            "action": "fase_tardia",
            "priority": "media",
            "title": "Jogo avançado",
            "reason": (
                "Após 75' a volatilidade sobe. Prefira mercados de linha (over/under) "
                "ou cash-out em apostas abertas."
            ),
        })

    if h2h_overround is not None and h2h_overround > 0.10:
        shields.append({
            "action": "margem_alta",
            "priority": "media",
            "title": "Margem 1X2 elevada",
            "reason": (
                f"Overround {h2h_overround * 100:.1f}% — exija EV maior para novos aportes "
                "e evite empilhar no 1X2."
            ),
        })

    shields.extend(_house_trap_shields(benchmark))
    shields.extend(_correlation_warnings(opportunities))
    shields.extend(_hedge_suggestions(user_bet, inplay, snapshot, threshold=threshold, minute=minute))

    if cashout and cashout["action"] in {"cashout", "cashout_parcial"}:
        shields.insert(0, {
            "action": cashout["action"],
            "priority": "alta",
            "title": "Blindagem da aposta aberta",
            "reason": cashout["reason"],
        })

    watch_list = all_edges[:3]
    wait_reason = _wait_reason(all_edges, threshold, minute)

    rules = [
        f"Postura atual: {posture.upper()} — exposição nova máx. {max_new_exposure_pct:.1f}% (R$ {bankroll * max_new_exposure_pct / 100:.0f})",
        "Máximo 1 aposta forte + 1 moderada no mesmo jogo",
        "Nunca somar stakes correlacionadas sem reduzir 50%",
        "Reavaliar a cada 3–5 minutos ou após gol",
        "Se EV residual da aposta aberta < -6%, cash-out parcial",
    ]
    if not opportunities:
        rules.append("Sem oportunidade com edge — aguardar é a melhor blindagem")

    return {
        "posture": posture,
        "max_new_exposure_pct": max_new_exposure_pct,
        "max_new_exposure_value": round(bankroll * max_new_exposure_pct / 100, 2),
        "opportunity_count": len(opportunities),
        "strong_opportunity_count": strong_ops,
        "min_edge_threshold": round(threshold, 4),
        "effective_threshold": round(effective_threshold, 4),
        "time_decay_confidence": round(decay, 2),
        "wait_reason": wait_reason,
        "watch_list": watch_list,
        "market_scan": all_edges,
        "opportunities": opportunities,
        "shields": shields,
        "rules": rules,
        "cashout": cashout,
    }


def _wait_reason(all_edges: list[dict[str, Any]], threshold: float, minute: int) -> str:
    if not all_edges:
        return (
            "A Superbet ainda não trouxe odds nos mercados que analisamos (1X2, totais, BTTS). "
            "Aguarde o próximo refresh (~25s)."
        )
    best = all_edges[0]
    ev_pct = best["expected_value"] * 100
    need_pct = threshold * 100
    if best["expected_value"] < 0:
        return (
            f"Nenhum mercado com valor positivo. O menos ruim é {best['label']} "
            f"(EV {ev_pct:.1f}%). Não aposte."
        )
    if best["expected_value"] < threshold:
        return (
            f"O mercado mais próximo é {best['label']} @ {best['market_odd']} "
            f"(EV +{ev_pct:.1f}%), mas o limiar in-play é +{need_pct:.0f}%. "
            f"Veja a lista abaixo ou aguarde gol / refresh (~25s)."
        )
    return f"Reavalie após gol ou em ~25s (minuto {minute}')."
