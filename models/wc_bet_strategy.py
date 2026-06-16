"""Plano de apostas in-play com oportunidades ranqueadas e regras de blindagem."""
from __future__ import annotations

from typing import Any

from config import settings
from ingest.superbet.parser import SuperbetEventSnapshot
from models.ev_value import evaluate_outcome
from models.wc_handicap_score import assess_handicap_vs_live_score, parse_any_handicap_market
from models.wc_bet_advice import (
    UserBetInput,
    _ht_scores_from_inplay,
    _market_odd,
    _prob_from_inplay,
    _score_from_inplay,
    advise_aportes,
    advise_cashout,
    is_aggressive_leading_handicap,
    parse_period_handicap_market,
    scan_all_market_edges,
)
from models.wc_bet_timing import assess_bet_timing, build_fundamentacao
from models.wc_team_patterns import build_combo_ticket, pattern_accuracy_score

_CORRELATION_GROUPS: list[frozenset[str]] = [
    frozenset({"h2h:1", "next_goal:home"}),
    frozenset({"h2h:2", "next_goal:away"}),
    frozenset({"over_2_5:yes", "btts:yes"}),
    frozenset({"over_2_5:yes", "over_3_5:yes"}),
]


def _market_key(market: str, outcome: str) -> str:
    return f"{market}:{outcome.lower()}"


def _tier_by_edge(edge_pp: float, min_edge_pp: float | None = None) -> str:
    """Classifica oportunidade pelo edge probabilístico (modelo vs mercado)."""
    min_pp = min_edge_pp or settings.live_min_edge_pp
    if edge_pp >= min_pp * 2.5:
        return "forte"
    if edge_pp >= min_pp * 1.5:
        return "moderada"
    if edge_pp >= min_pp:
        return "leve"
    return "abaixo_limiar"


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


def _aggressive_handicap_shields(
    *,
    home_team: str,
    away_team: str,
    inplay: dict[str, Any],
    minute: int,
    all_edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Alerta quando favorito já lidera e handicaps ≤ −1 no 2T parecem atrativos."""
    if minute < 45:
        return []

    home_sc, away_sc = _score_from_inplay(inplay)
    gap = home_sc - away_sc
    if gap >= 1:
        leader_name = home_team
    elif gap <= -1:
        leader_name = away_team
    else:
        return []

    score_str = f"{home_sc}x{away_sc}"
    shields: list[dict[str, Any]] = [
        {
            "action": "evitar",
            "priority": "alta",
            "title": f"Evitar handicap agressivo no 2º tempo ({leader_name})",
            "reason": (
                f"{leader_name} já lidera {score_str}. Handicaps −1 ou piores no 2T "
                f"(ex.: −1.5, −2.5) exigem goleada no período — cenário improvável com "
                f"jogo controlado. Prefira over 0.5 no 2T ou handicap −0.5 / empate anula."
            ),
        },
    ]

    for row in all_edges:
        blocked, detail = is_aggressive_leading_handicap(
            row["market"],
            inplay,
            minute=minute,
        )
        if not blocked or row.get("expected_value", 0) <= 0:
            continue
        shields.append({
            "action": "evitar",
            "priority": "alta",
            "title": f"Armadilha: {row['label']}",
            "reason": (
                f"Odd {row['market_odd']:.2f} parece atrativa (EV +{row['expected_value'] * 100:.1f}%), "
                f"mas {detail}. Não recomendamos este aporte."
            ),
            "market": row["market"],
            "outcome": row.get("outcome", "yes"),
            "odd": row["market_odd"],
            "expected_value": row["expected_value"],
        })
    return shields


def _trailing_handicap_shields(
    *,
    home_team: str,
    away_team: str,
    inplay: dict[str, Any],
    minute: int,
    all_edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Alerta quando handicap negativo é sugerido para time que está perdendo."""
    home_sc, away_sc = _score_from_inplay(inplay)
    ht_h, ht_a = _ht_scores_from_inplay(inplay)
    shields: list[dict[str, Any]] = []

    for row in all_edges:
        market = row.get("market", "")
        if not (parse_any_handicap_market(market) or parse_period_handicap_market(market)):
            continue
        if row.get("expected_value", 0) <= 0:
            continue
        assessment = assess_handicap_vs_live_score(
            market,
            home_score=home_sc,
            away_score=away_sc,
            minute=minute,
            ht_home=ht_h,
            ht_away=ht_a,
            home_team=home_team,
            away_team=away_team,
        )
        if assessment is None or assessment.status != "needs_win":
            continue
        shields.append({
            "action": "cautela",
            "priority": "alta",
            "title": f"Handicap exige virada: {row['label']}",
            "reason": (
                f"Placar {home_sc}×{away_sc}. {assessment.score_hint}. "
                f"A probabilidade do modelo ({row['model_prob'] * 100:.0f}%) "
                f"já considera o placar — só aporte se a virada for provável."
            ),
            "market": market,
            "outcome": row.get("outcome", "yes"),
            "odd": row["market_odd"],
            "expected_value": row["expected_value"],
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
    confidence: dict[str, Any] | None = None,
    event_id: int | None = None,
    fast: bool = False,
) -> dict[str, Any]:
    conf_score = float((confidence or {}).get("score") or 1.0)
    min_edge_pp = settings.live_min_edge_pp
    if conf_score < 0.5:
        min_edge_pp = max(min_edge_pp, 10.0)

    all_edges, threshold = scan_all_market_edges(
        inplay,
        snapshot,
        bankroll=bankroll,
        live=True,
        home_team=home_team,
        away_team=away_team,
        minute=minute,
    )
    aportes = advise_aportes(
        inplay,
        snapshot,
        bankroll=bankroll,
        max_recommendations=8,
        live=True,
        home_team=home_team,
        away_team=away_team,
        minute=minute,
        confidence_score=conf_score,
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
    block_all_new = minute > settings.live_block_2h_minute
    decay = _time_decay_confidence(minute)
    effective_threshold = threshold / decay if decay > 0 else threshold
    if not block_all_new:
        rank = 0
        for a in aportes:
            tier = _tier_by_edge(a.edge_pp, min_edge_pp)
            if conf_score < 0.5 and tier in {"leve", "moderada"}:
                continue
            rank += 1
            stake_pct = a.suggested_stake_pct
            if tier == "leve":
                stake_pct = round(min(stake_pct, 1.5), 2)
            if minute >= 80:
                stake_pct = round(stake_pct * 0.6, 2)
            elif minute >= 75:
                stake_pct = round(stake_pct * 0.8, 2)

            opp: dict[str, Any] = {
                "rank": rank,
                "market": a.market,
                "outcome": a.outcome,
                "label": a.label,
                "tier": tier,
                "model_prob": a.model_prob,
                "market_odd": a.market_odd,
                "implied_prob": a.implied_prob,
                "expected_value": a.expected_value,
                "edge_pp": a.edge_pp,
                "suggested_stake_pct": stake_pct,
                "suggested_stake_value": round(bankroll * stake_pct / 100, 2),
                "action": a.action,
            }
            if not fast:
                timing = assess_bet_timing(
                    event_id=event_id,
                    market=a.market,
                    outcome=a.outcome,
                    model_prob=a.model_prob,
                    implied_prob=a.implied_prob,
                )
                fundamentacao = build_fundamentacao(
                    confidence=confidence,
                    market=a.market,
                    model_prob=a.model_prob,
                    implied_prob=a.implied_prob,
                    edge_pp=a.edge_pp,
                    minute=minute,
                )
                opp["timing"] = timing["timing"]
                opp["timing_reason"] = timing["timing_reason"]
                opp["fundamentacao"] = fundamentacao
            opportunities.append(opp)

    strong_ops = sum(1 for o in opportunities if o["tier"] in {"forte", "moderada"})
    if block_all_new:
        posture = "defensivo"
    else:
        posture = _posture(
            cashout_action=cashout["action"] if cashout else None,
            strong_ops=strong_ops,
            minute=minute,
            remaining_ev=remaining_ev,
        )

    total_exposure_pct = round(sum(o["suggested_stake_pct"] for o in opportunities[:3]), 2)
    max_new_exposure_pct = min(5.0, total_exposure_pct) if posture != "defensivo" else min(2.0, total_exposure_pct)

    shields: list[dict[str, Any]] = []

    if confidence and conf_score < 0.25:
        shields.append({
            "action": "aguardar",
            "priority": "alta",
            "title": "Modelo sem dados suficientes",
            "reason": (
                confidence.get("reason")
                or "Não há histórico confiável para estes times. "
                "Não recomendamos apostas — aguarde mais contexto ou use mercados "
                "com dados Sofascore/FIFA carregados."
            ),
        })
    elif confidence and conf_score < 0.5:
        shields.append({
            "action": "aguardar",
            "priority": "media",
            "title": "Confiança baixa nos dados",
            "reason": (
                f"{confidence.get('reason', '')} "
                "Só entram recomendações com edge ≥ 8 pp."
            ).strip(),
        })

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

    if minute > settings.live_block_2h_minute:
        shields.insert(0, {
            "action": "evitar",
            "priority": "alta",
            "title": "Janela fechada para aportes",
            "reason": (
                f"Após {settings.live_block_2h_minute}' só cash-out. "
                "Pouco tempo restante para mercados de 2T."
            ),
        })
    elif minute >= settings.live_block_minute:
        shields.insert(0, {
            "action": "aguardar",
            "priority": "media",
            "title": "Só mercados do 2º tempo",
            "reason": (
                f"Mercados do jogo inteiro bloqueados após {settings.live_block_minute}'. "
                f"Sugestões limitadas ao 2T até {settings.live_block_2h_minute}'."
            ),
        })
    elif minute >= settings.live_midgame_strict_minute:
        shields.insert(0, {
            "action": "aguardar",
            "priority": "alta",
            "title": "2º tempo — edge elevado",
            "reason": (
                f"A partir de {settings.live_midgame_strict_minute}' exigimos "
                f"≥{settings.live_midgame_min_edge_pp:.0f} pp de vantagem. "
                "Prefira apostas no 1º tempo ou cash-out."
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

    if not fast:
        shields.extend(_house_trap_shields(benchmark))
        shields.extend(
            _aggressive_handicap_shields(
                home_team=home_team,
                away_team=away_team,
                inplay=inplay,
                minute=minute,
                all_edges=all_edges,
            )
        )
        shields.extend(
            _trailing_handicap_shields(
                home_team=home_team,
                away_team=away_team,
                inplay=inplay,
                minute=minute,
                all_edges=all_edges,
            )
        )
        shields.extend(_correlation_warnings(opportunities))
        shields.extend(
            _hedge_suggestions(user_bet, inplay, snapshot, threshold=threshold, minute=minute)
        )

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

    if fast:
        pattern_accuracy = None
        combo_ticket = None
    else:
        pattern_accuracy = pattern_accuracy_score(home_team, away_team)
        combo_ticket = build_combo_ticket(
            home_team, away_team, bankroll=bankroll, snapshot=snapshot
        )
        if pattern_accuracy["score"] >= 0.45 and combo_ticket.get("available"):
            rules.append(
                "Bilhete combo KXL disponível — use a seção abaixo; "
                "não duplique stakes no combo e nas oportunidades EV."
            )

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
        "pattern_accuracy": pattern_accuracy,
        "combo_ticket": combo_ticket,
    }


def _wait_reason(all_edges: list[dict[str, Any]], threshold: float, minute: int) -> str:
    if minute > settings.live_block_2h_minute:
        return (
            f"Após {settings.live_block_2h_minute}' não recomendamos novos aportes — "
            "só cash-out ou aguardar."
        )
    if minute >= settings.live_block_minute:
        return (
            f"Mercados FT bloqueados após {settings.live_block_minute}'. "
            f"Foque em mercados do 2º tempo (até {settings.live_block_2h_minute}')."
        )
    if minute >= settings.live_midgame_strict_minute:
        return (
            f"2º tempo ({minute}') — exigimos edge ≥{settings.live_midgame_min_edge_pp:.0f} pp "
            f"e EV ×{settings.live_midgame_ev_multiplier:.1f}. Monitore; evite entradas impulsivas."
        )
    if not all_edges:
        return (
            "A Superbet ainda não trouxe odds nos mercados que analisamos (1X2, totais, BTTS). "
            "Aguarde o próximo refresh (~25s)."
        )
    best = all_edges[0]
    edge = best.get("edge_pp", 0)
    min_pp = settings.live_min_edge_pp
    if edge < 0:
        return (
            f"Nenhum mercado com vantagem probabilística. O menos ruim é {best['label']} "
            f"(edge {edge:.1f} pp). Não aposte."
        )
    if edge < min_pp:
        return (
            f"O melhor mercado agora é {best['label']} (edge +{edge:.1f} pp), "
            f"mas ainda abaixo do mínimo de {min_pp:.0f} pp. Monitore a linha nos próximos refreshes."
        )
    if minute >= 80:
        return "Jogo avançado — exigimos edge maior para recomendar entrada."
    return (
        f"Edge insuficiente no momento. Melhor leitura: {best['label']} (+{edge:.1f} pp)."
    )
