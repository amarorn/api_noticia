"""Recomendações de cash-out e aporte com base no modelo in-play vs mercado."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from config import settings
from models.economics import coase_effective_min_edge, live_effective_min_edge
from models.ev_value import evaluate_outcome
from ingest.superbet.parser import SuperbetEventSnapshot


@dataclass
class UserBetInput:
    market: str
    outcome: str
    stake: float
    odds_placed: float


@dataclass
class CashoutAdvice:
    action: str
    confidence: float
    reason: str
    current_model_prob: float
    placed_implied_prob: float
    remaining_ev: float
    estimated_fair_cashout: float
    potential_return: float


@dataclass
class AporteAdvice:
    market: str
    outcome: str
    label: str
    model_prob: float
    market_odd: float
    implied_prob: float
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    suggested_stake_pct: float
    action: str


def _prob_from_inplay(inplay: dict[str, Any], market: str, outcome: str) -> float | None:
    key = f"{market}:{outcome}".lower()
    mapping: dict[str, float] = {
        "h2h:1": inplay.get("prob_final_home", 0),
        "h2h:x": inplay.get("prob_final_draw", 0),
        "h2h:2": inplay.get("prob_final_away", 0),
        "h2h:0": inplay.get("prob_final_draw", 0),
        "next_goal:home": inplay.get("prob_next_goal_home", 0),
        "next_goal:away": inplay.get("prob_next_goal_away", 0),
        "next_goal:none": inplay.get("prob_no_more_goals", 0),
        "btts:yes": inplay.get("btts_final", 0),
        "btts:no": 1.0 - float(inplay.get("btts_final", 0)),
        "over_2_5:yes": inplay.get("final_line_probs", {}).get("over_2_5", 0),
        "over_2_5:no": inplay.get("final_line_probs", {}).get("under_2_5", 0),
        "over_3_5:yes": inplay.get("final_line_probs", {}).get("over_3_5", 0),
        "over_3_5:no": inplay.get("final_line_probs", {}).get("under_3_5", 0),
        "combo_btts_over_3_5:yes": inplay.get("combo_markets", {}).get("btts_and_over_3_5", 0),
        "combo_btts_over_3_5:no": 1.0 - float(inplay.get("combo_markets", {}).get("btts_and_over_3_5", 0)),
    }
    if key in mapping:
        return float(mapping[key])
    combo = inplay.get("combo_markets", {})
    if market in combo and outcome in {"yes", "sim"}:
        return float(combo[market])
    return None


def _effective_min_edge(*, min_edge: float | None, live: bool) -> float:
    if live:
        return live_effective_min_edge(min_edge)
    return coase_effective_min_edge(min_edge or settings.ev_min_edge)


def _market_odd(snapshot: SuperbetEventSnapshot | None, market: str, outcome: str) -> float | None:
    if snapshot is None:
        return None
    out = outcome.upper()
    if market == "h2h":
        key = "X" if out in {"X", "0", "DRAW", "EMPATE"} else out
        return snapshot.h2h_odds.get(key)
    if market.startswith("over_"):
        line = market.replace("over_", "").replace("_", ".")
        prices = snapshot.totals.get(line) or {}
        for name, price in prices.items():
            if outcome in {"yes", "sim"} and "mais" in name.lower():
                return price
            if outcome in {"no", "não", "nao"} and "menos" in name.lower():
                return price
    if market == "btts":
        key = "yes" if outcome.lower() in {"yes", "sim"} else "no"
        return (snapshot.btts_odds or {}).get(key)
    if market == "next_goal":
        return (snapshot.next_goal_odds or {}).get(outcome.lower())
    return None


def advise_cashout(
    bet: UserBetInput,
    inplay: dict[str, Any],
    *,
    minute: int = 0,
    book_margin: float = 0.08,
) -> CashoutAdvice:
    current_p = _prob_from_inplay(inplay, bet.market, bet.outcome)
    if current_p is None:
        return CashoutAdvice(
            action="aguardar",
            confidence=0.0,
            reason="Mercado da aposta não mapeado no modelo in-play.",
            current_model_prob=0.0,
            placed_implied_prob=0.0,
            remaining_ev=0.0,
            estimated_fair_cashout=bet.stake,
            potential_return=bet.stake * bet.odds_placed,
        )

    placed_implied = 1.0 / max(bet.odds_placed, 1.01)
    remaining_ev = current_p * bet.odds_placed - 1.0
    potential = bet.stake * bet.odds_placed
    estimated_fair = bet.stake * (1.0 + (bet.odds_placed - 1.0) * current_p) * (1.0 - book_margin)

    prob_ratio = current_p / max(placed_implied, 1e-6)
    late_game = minute >= 80

    if remaining_ev < -0.10 or prob_ratio < 0.65:
        action = "cashout"
        reason = (
            "O modelo indica que a chance de ganhar caiu bastante em relação à odd que você pegou. "
            "Cash-out protege o que ainda resta de valor."
        )
        confidence = min(0.95, 0.7 + abs(remaining_ev))
    elif remaining_ev < -0.04 or (prob_ratio < 0.80 and late_game):
        action = "cashout_parcial"
        reason = (
            "EV residual negativo ou jogo avançado com probabilidade abaixo da entrada. "
            "Considere cash-out parcial (50–70% do valor oferecido)."
        )
        confidence = 0.65
    elif remaining_ev > 0.06 and prob_ratio > 1.05:
        action = "manter"
        reason = (
            "O modelo ainda vê valor na sua aposta em relação à odd de entrada. "
            "Não há sinal forte para cash-out."
        )
        confidence = min(0.9, 0.55 + remaining_ev)
    else:
        action = "aguardar"
        reason = (
            "Cenário neutro: nem proteção urgente nem valor claro para dobrar. "
            "Monitore a cada 3–5 minutos."
        )
        confidence = 0.5

    return CashoutAdvice(
        action=action,
        confidence=round(confidence, 3),
        reason=reason,
        current_model_prob=round(current_p, 4),
        placed_implied_prob=round(placed_implied, 4),
        remaining_ev=round(remaining_ev, 4),
        estimated_fair_cashout=round(estimated_fair, 2),
        potential_return=round(potential, 2),
    )


def _aporte_candidates(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    home_team: str = "Casa",
    away_team: str = "Fora",
) -> list[tuple[str, str, str, float, float]]:
    """market, outcome, label, model_prob, market_odd"""
    candidates: list[tuple[str, str, str, float, float]] = []
    specs: list[tuple[str, str, str, Callable[[], float | None]]] = [
        ("h2h", "1", f"{home_team} vence", lambda: inplay.get("prob_final_home")),
        ("h2h", "X", "Empate", lambda: inplay.get("prob_final_draw")),
        ("h2h", "2", f"{away_team} vence", lambda: inplay.get("prob_final_away")),
        ("over_2_5", "yes", "Over 2.5 gols", lambda: inplay.get("final_line_probs", {}).get("over_2_5")),
        ("over_3_5", "yes", "Over 3.5 gols", lambda: inplay.get("final_line_probs", {}).get("over_3_5")),
        ("btts", "yes", "Ambos marcam", lambda: inplay.get("btts_final")),
        ("next_goal", "home", f"Próximo gol {home_team}", lambda: inplay.get("prob_next_goal_home")),
        ("next_goal", "away", f"Próximo gol {away_team}", lambda: inplay.get("prob_next_goal_away")),
    ]
    for market, outcome, label, prob_fn in specs:
        prob = prob_fn()
        if prob is None or prob <= 0:
            continue
        odd = _market_odd(snapshot, market, outcome)
        if odd is None or odd <= 1.0:
            continue
        candidates.append((market, outcome, label, float(prob), float(odd)))
    return candidates


def scan_all_market_edges(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    bankroll: float | None = None,
    min_edge: float | None = None,
    live: bool = False,
    home_team: str = "Casa",
    away_team: str = "Fora",
) -> tuple[list[dict[str, Any]], float]:
    """Todos os mercados mapeados com EV, ordenados do maior para o menor."""
    threshold = _effective_min_edge(min_edge=min_edge, live=live)
    bankroll = bankroll or 1000.0
    rows: list[dict[str, Any]] = []

    for market, outcome, label, prob, odd in _aporte_candidates(
        inplay, snapshot, home_team=home_team, away_team=away_team,
    ):
        ev = evaluate_outcome(outcome, prob, odd)
        edge_pp = (prob - ev.implied_prob) * 100
        kelly_q = ev.kelly_quarter
        suggested_pct = round(min(5.0, kelly_q * 100), 2)
        rows.append({
            "market": market,
            "outcome": outcome,
            "label": label,
            "model_prob": round(prob, 4),
            "market_odd": round(odd, 3),
            "implied_prob": round(ev.implied_prob, 4),
            "expected_value": round(ev.expected_value, 4),
            "edge_pp": round(edge_pp, 2),
            "suggested_stake_pct": suggested_pct,
            "suggested_stake_value": round(bankroll * suggested_pct / 100, 2),
            "meets_threshold": ev.expected_value >= threshold,
        })

    rows.sort(key=lambda x: x["expected_value"], reverse=True)
    return rows, threshold


def advise_aportes(
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    *,
    bankroll: float | None = None,
    min_edge: float | None = None,
    max_recommendations: int = 5,
    live: bool = False,
    home_team: str = "Casa",
    away_team: str = "Fora",
) -> list[AporteAdvice]:
    threshold = _effective_min_edge(min_edge=min_edge, live=live)
    bankroll = bankroll or 1000.0
    out: list[AporteAdvice] = []

    for market, outcome, label, prob, odd in _aporte_candidates(
        inplay, snapshot, home_team=home_team, away_team=away_team,
    ):
        ev = evaluate_outcome(outcome, prob, odd)
        edge_pp = (prob - ev.implied_prob) * 100
        if ev.expected_value < threshold:
            continue
        kelly_q = ev.kelly_quarter
        suggested_pct = round(min(5.0, kelly_q * 100), 2)
        action = "aportar" if ev.expected_value >= threshold * 2 else "aportar_pequeno"
        out.append(
            AporteAdvice(
                market=market,
                outcome=outcome,
                label=label,
                model_prob=round(prob, 4),
                market_odd=round(odd, 3),
                implied_prob=round(ev.implied_prob, 4),
                expected_value=round(ev.expected_value, 4),
                edge_pp=round(edge_pp, 2),
                kelly_quarter=round(kelly_q, 4),
                suggested_stake_pct=suggested_pct,
                action=action,
            )
        )

    out.sort(key=lambda x: x.expected_value, reverse=True)
    return out[:max_recommendations]


def build_bet_advice_report(
    *,
    home_team: str,
    away_team: str,
    inplay: dict[str, Any],
    snapshot: SuperbetEventSnapshot | None,
    user_bet: UserBetInput | None,
    minute: int = 0,
    bankroll: float | None = None,
) -> dict[str, Any]:
    cashout = None
    if user_bet is not None:
        cashout = advise_cashout(user_bet, inplay, minute=minute)
    aportes = advise_aportes(
        inplay, snapshot, bankroll=bankroll, live=True, home_team=home_team, away_team=away_team,
    )
    return {
        "home_team": home_team,
        "away_team": away_team,
        "minute": minute,
        "current_score": inplay.get("current_score"),
        "cashout": None if cashout is None else {
            "action": cashout.action,
            "confidence": cashout.confidence,
            "reason": cashout.reason,
            "current_model_prob": cashout.current_model_prob,
            "placed_implied_prob": cashout.placed_implied_prob,
            "remaining_ev": cashout.remaining_ev,
            "estimated_fair_cashout": cashout.estimated_fair_cashout,
            "potential_return": cashout.potential_return,
        },
        "aportes": [
            {
                "market": a.market,
                "outcome": a.outcome,
                "label": a.label,
                "model_prob": a.model_prob,
                "market_odd": a.market_odd,
                "implied_prob": a.implied_prob,
                "expected_value": a.expected_value,
                "edge_pp": a.edge_pp,
                "kelly_quarter": a.kelly_quarter,
                "suggested_stake_pct": a.suggested_stake_pct,
                "suggested_stake_value": round((bankroll or 1000) * a.suggested_stake_pct / 100, 2),
                "action": a.action,
            }
            for a in aportes
        ],
    }
