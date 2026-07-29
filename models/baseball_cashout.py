"""Cash-out in-play para apostas abertas de beisebol."""
from __future__ import annotations

from typing import Any

from config import settings
from models.wc_bet_advice import CashoutAdvice, UserBetInput


def _prob_from_baseball_inplay(
    inplay: dict[str, Any],
    market: str,
    outcome: str,
) -> float | None:
    """Mapeia mercado/outcome da aposta → probabilidade do modelo in-play."""
    side = (outcome or "").lower()
    ml = inplay.get("moneyline_probs") or {}
    spread = inplay.get("spread_probs") or {}
    totals = inplay.get("total_probs") or {}
    team_totals = inplay.get("team_total_probs") or {}
    period = inplay.get("period_probs") or {}

    if market == "moneyline":
        key = outcome if outcome in {"1", "2"} else None
        if key and key in ml:
            return float(ml[key])
        if outcome == "1":
            return float(inplay.get("prob_home_win") or 0)
        if outcome == "2":
            return float(inplay.get("prob_away_win") or 0)
        return None

    if market == "spread" and side in spread:
        return float(spread[side])

    if market == "total_runs" and side in totals:
        return float(totals[side])

    if market == "team_total_runs" and side in team_totals:
        return float(team_totals[side])

    if market.startswith("f5_"):
        if side in period:
            return float(period[side])
        alt = f"f5_{side}" if not side.startswith("f5_") else side
        if alt in period:
            return float(period[alt])

    if market == "inning_total" and side in period:
        return float(period[side])

    if market == "inning_1x2" and side in period:
        return float(period[side])

    if market == "run_n" and side in period:
        return float(period[side])

    return None


def advise_baseball_cashout(
    bet: UserBetInput,
    inplay: dict[str, Any],
    *,
    inning: int = 1,
    book_margin: float = 0.08,
) -> CashoutAdvice:
    """Recomendação de cash-out espelhando wc_bet_advice (adaptado por entrada)."""
    current_p = _prob_from_baseball_inplay(inplay, bet.market, bet.outcome)
    if current_p is None:
        return CashoutAdvice(
            action="aguardar",
            confidence=0.0,
            reason="Mercado da aposta não mapeado no modelo in-play de beisebol.",
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
    late_game = inning >= settings.baseball_late_inning

    if remaining_ev < -0.10 or prob_ratio < 0.65:
        action = "cashout"
        reason = (
            "A chance de ganhar caiu bastante vs a odd de entrada. "
            "Cash-out protege o valor restante."
        )
        confidence = min(0.95, 0.7 + abs(remaining_ev))
    elif remaining_ev < -0.04 or (prob_ratio < 0.80 and late_game):
        action = "cashout_parcial"
        reason = (
            "EV residual negativo ou reta final com probabilidade abaixo da entrada. "
            "Considere cash-out parcial (50–70%)."
        )
        confidence = 0.65
    elif remaining_ev > 0.06 and prob_ratio > 1.05:
        action = "manter"
        reason = "O modelo ainda vê valor na aposta vs odd de entrada."
        confidence = min(0.9, 0.55 + remaining_ev)
    else:
        action = "aguardar"
        reason = "Cenário neutro — monitore a cada entrada."
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


def cashout_to_dict(advice: CashoutAdvice) -> dict[str, Any]:
    return {
        "action": advice.action,
        "confidence": advice.confidence,
        "reason": advice.reason,
        "current_model_prob": advice.current_model_prob,
        "placed_implied_prob": advice.placed_implied_prob,
        "remaining_ev": advice.remaining_ev,
        "estimated_fair_cashout": advice.estimated_fair_cashout,
        "potential_return": advice.potential_return,
        "trend_influenced": advice.trend_influenced,
        "trend_urgency": advice.trend_urgency,
    }
