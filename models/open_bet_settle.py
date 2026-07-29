"""Liquidação automática de apostas abertas ao encerrar evento Superbet."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from models.bet_market_infer import infer_other_market

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


def _parse_baseball_total_outcome(outcome: str) -> tuple[str, float] | None:
    """Extrai lado (over/under) e linha de outcomes como ``over_8_5`` ou ``f5_under_4_5``."""
    raw = outcome.lower()
    for side in ("over", "under"):
        token = f"{side}_"
        if token in raw:
            suffix = raw[raw.rfind(token) + len(token) :]
            try:
                return side, float(suffix.replace("_", "."))
            except ValueError:
                return None
    return None


def _parse_spread_outcome(outcome: str) -> tuple[str, float] | None:
    """Parse ``home_m1_5`` / ``away_p0_5`` (prefixo ``f5_`` opcional)."""
    raw = outcome.lower()
    if raw.startswith("f5_"):
        raw = raw[3:]
    if not (raw.startswith("home_") or raw.startswith("away_")):
        return None
    side, rest = raw.split("_", 1)
    if rest.startswith("m"):
        sign = -1
        num = rest[1:]
    elif rest.startswith("p"):
        sign = 1
        num = rest[1:]
    else:
        return None
    try:
        return side, sign * float(num.replace("_", "."))
    except ValueError:
        return None


def _cumulative_inning_score(
    baseball_innings: list[dict[str, Any]] | None,
    through_inning: int,
) -> tuple[int, int] | None:
    if not baseball_innings:
        return None
    home = away = 0
    for row in baseball_innings:
        num = int(row.get("num") or 0)
        if num <= through_inning:
            home += int(row.get("home") or 0)
            away += int(row.get("away") or 0)
    return home, away


def _spread_covers(side: str, line: float, home_score: int, away_score: int) -> bool:
    if side == "home":
        return home_score + line > away_score
    return away_score + line > home_score


def _normalize_pick(
    market: str,
    outcome: str,
    target_value: str | None,
) -> tuple[str, str, str | None]:
    """Normaliza mercado legado ``other`` para forma avaliável."""
    market_l = (market or "").lower()
    if market_l != "other":
        if market_l in {"moneyline", "ml"}:
            return "h2h", (outcome or "").lower(), target_value
        if market_l in {"spread", "run_line"}:
            return "run_line", (outcome or "").lower(), target_value
        return market_l, (outcome or "").lower(), target_value

    inferred = infer_other_market(outcome, target_value)
    if inferred:
        return inferred
    return market_l, (outcome or "").lower(), target_value


def evaluate_pick(
    *,
    market: str,
    outcome: str,
    target_value: str | None,
    home_score: int,
    away_score: int,
    home_corners: int | None = None,
    away_corners: int | None = None,
    baseball_innings: list[dict[str, Any]] | None = None,
) -> bool | None:
    """Avalia se um palpite ganhou. ``None`` = não avaliável (ex.: próximo gol)."""
    market, outcome, target_value = _normalize_pick(market, outcome, target_value)
    total_goals = home_score + away_score
    total_corners = (home_corners or 0) + (away_corners or 0)

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
            return total_goals > line
        if outcome == "under":
            return total_goals < line
        return None

    if market == "corners_total":
        line = _parse_line(market, target_value)
        if line is None:
            return None
        if home_corners is None and away_corners is None:
            return None
        if outcome == "over":
            return total_corners > line
        if outcome == "under":
            return total_corners < line
        return None

    if market == "odd_even_goals":
        is_even = total_goals % 2 == 0
        if outcome in ("even", "par"):
            return is_even
        if outcome in ("odd", "impar", "ímpar"):
            return not is_even
        return None

    if market == "odd_even_corners":
        if home_corners is None and away_corners is None:
            return None
        is_even = total_corners % 2 == 0
        if outcome in ("even", "par"):
            return is_even
        if outcome in ("odd", "impar", "ímpar"):
            return not is_even
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

    if market == "total_runs":
        parsed = _parse_baseball_total_outcome(outcome)
        if parsed is None:
            line = _parse_line(market, target_value)
            if line is None:
                return None
            if outcome == "over":
                return total_goals > line
            if outcome == "under":
                return total_goals < line
            return None
        side, line = parsed
        if side == "over":
            return total_goals > line
        if side == "under":
            return total_goals < line
        return None

    if market == "team_total_runs":
        raw = outcome.lower()
        team_score = None
        if raw.startswith("home_over_") or raw.startswith("home_under_"):
            team_score = home_score
            parsed = _parse_baseball_total_outcome(raw.replace("home_", "", 1))
        elif raw.startswith("away_over_") or raw.startswith("away_under_"):
            team_score = away_score
            parsed = _parse_baseball_total_outcome(raw.replace("away_", "", 1))
        else:
            return None
        if team_score is None or parsed is None:
            return None
        side, line = parsed
        if side == "over":
            return team_score > line
        if side == "under":
            return team_score < line
        return None

    if market in {"run_line", "f5_spread"}:
        spread_outcome = outcome[3:] if market == "f5_spread" and outcome.startswith("f5_") else outcome
        parsed = _parse_spread_outcome(spread_outcome)
        if parsed is None:
            return None
        side, line = parsed
        if market == "f5_spread":
            f5 = _cumulative_inning_score(baseball_innings, 5)
            if f5 is None:
                return None
            fh, fa = f5
            return _spread_covers(side, line, fh, fa)
        return _spread_covers(side, line, home_score, away_score)

    if market == "f5_total":
        parsed = _parse_baseball_total_outcome(outcome if outcome.startswith("f5_") else f"f5_{outcome}")
        f5 = _cumulative_inning_score(baseball_innings, 5)
        if parsed is None or f5 is None:
            return None
        side, line = parsed
        total = f5[0] + f5[1]
        if side == "over":
            return total > line
        if side == "under":
            return total < line
        return None

    if market == "f5_moneyline":
        f5 = _cumulative_inning_score(baseball_innings, 5)
        if f5 is None:
            return None
        fh, fa = f5
        key = outcome.lower()
        if key.startswith("f5_ml_"):
            key = key[6:]
        if key in ("1", "home"):
            return fh > fa
        if key in ("2", "away"):
            return fa > fh
        if key in ("x", "draw"):
            return fh == fa
        return None

    return None


def evaluate_bet_picks(
    picks: list[dict[str, Any]],
    home_score: int,
    away_score: int,
    *,
    home_corners: int | None = None,
    away_corners: int | None = None,
    baseball_innings: list[dict[str, Any]] | None = None,
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
            home_corners=home_corners,
            away_corners=away_corners,
            baseball_innings=baseball_innings,
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
    home_corners: int | None = None,
    away_corners: int | None = None,
    baseball_innings: list[dict[str, Any]] | None = None,
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
        won = evaluate_bet_picks(
            picks,
            home_score,
            away_score,
            home_corners=home_corners,
            away_corners=away_corners,
            baseball_innings=baseball_innings,
        )
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
