"""Liquidação automática de apostas abertas ao encerrar evento Superbet."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SettleEventResult:
    """Resumo da liquidação pós-jogo."""

    event_id: int
    final_score: str
    n_matched: int = 0
    n_settled: int = 0
    n_skipped: int = 0
    settled_ids: list[str] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)


def _parse_line(market: str, target_value: str | None) -> float | None:
    if target_value:
        try:
            return float(str(target_value).replace(",", "."))
        except ValueError:
            pass
    if market.startswith("totals_"):
        suffix = market.split("_", 1)[1]
        try:
            return float(suffix.replace("_", "."))
        except ValueError:
            return None
    return None


def evaluate_pick(
    *,
    market: str,
    outcome: str,
    target_value: str | None,
    home_score: int,
    away_score: int,
) -> bool | None:
    """Avalia se um palpite ganhou. ``None`` = não avaliável (ex.: próximo gol)."""
    market = (market or "").lower()
    outcome = (outcome or "").lower()
    total = home_score + away_score

    if market == "h2h":
        if outcome in ("home", "1"):
            return home_score > away_score
        if outcome in ("away", "2"):
            return away_score > home_score
        if outcome in ("draw", "x"):
            return home_score == away_score
        return None

    if market.startswith("totals") or market == "totals":
        line = _parse_line(market, target_value)
        if line is None:
            line = 2.5
        if outcome == "over":
            return total > line
        if outcome == "under":
            return total < line
        return None

    if market == "btts":
        both = home_score > 0 and away_score > 0
        if outcome == "yes":
            return both
        if outcome == "no":
            return not both
        return None

    if market == "next_goal":
        return None

    return None


def evaluate_bet_picks(
    picks: list[dict[str, Any]],
    home_score: int,
    away_score: int,
) -> bool | None:
    """Combo: todos os palpites precisam ganhar. ``None`` se algum não for avaliável."""
    if not picks:
        return None
    for pick in picks:
        won = evaluate_pick(
            market=str(pick.get("market", "")),
            outcome=str(pick.get("outcome", "")),
            target_value=pick.get("target_value"),
            home_score=home_score,
            away_score=away_score,
        )
        if won is None:
            return None
        if not won:
            return False
    return True


def _profit_for_result(stake: float, odds_placed: float, potential_return: float, won: bool) -> float:
    if won:
        ret = potential_return if potential_return > 0 else stake * odds_placed
        return round(ret - stake, 2)
    return round(-stake, 2)


def settle_open_bets_for_event(
    *,
    event_id: int,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    final_score: str | None = None,
) -> SettleEventResult:
    """Move apostas abertas do evento para ``user_settled_bets.json``."""
    from api.user_bets_store import get_bets_for_event, move_open_to_settled

    score_str = final_score or f"{home_score}x{away_score}"
    result = SettleEventResult(
        event_id=event_id,
        final_score=score_str,
    )

    open_bets = get_bets_for_event(home_team, away_team, status="open")
    # Também por event_id Superbet
    if event_id:
        from api.user_bets_store import list_open_bets

        seen_ids = {b.get("id") for b in open_bets}
        for bet in list_open_bets():
            if bet.superbet_event_id == event_id and bet.id not in seen_ids:
                open_bets.append(bet.model_dump(mode="json"))
                seen_ids.add(bet.id)

    result.n_matched = len(open_bets)
    settled_at = datetime.now(UTC).isoformat()

    for bet in open_bets:
        bet_id = bet.get("id") or ""
        picks = bet.get("picks") or []
        won = evaluate_bet_picks(picks, home_score, away_score)
        if won is None:
            result.n_skipped += 1
            result.skipped.append(
                {
                    "id": bet_id,
                    "reason": "mercado_nao_avaliavel",
                    "market": picks[0].get("market", "") if picks else "",
                }
            )
            continue

        stake = float(bet.get("stake") or 0)
        odds = float(bet.get("odds_placed") or 0)
        potential = float(bet.get("potential_return") or 0)
        profit = _profit_for_result(stake, odds, potential, won)

        settled = move_open_to_settled(
            bet_id,
            {
                "result": "won" if won else "lost",
                "profit": profit,
                "settled_at": settled_at,
                "final_score": score_str,
                "superbet_event_id": bet.get("superbet_event_id") or event_id,
                "source": bet.get("source") or "event_finalize",
            },
        )
        if settled:
            result.n_settled += 1
            result.settled_ids.append(bet_id)
            logger.info(
                "aposta_liquidada",
                bet_id=bet_id,
                event_id=event_id,
                result=settled.result,
                profit=profit,
            )
        else:
            result.n_skipped += 1
            result.skipped.append({"id": bet_id, "reason": "nao_encontrada_no_store"})

    return result


__all__ = [
    "SettleEventResult",
    "evaluate_bet_picks",
    "evaluate_pick",
    "settle_open_bets_for_event",
]
