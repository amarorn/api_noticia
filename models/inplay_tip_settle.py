"""Liquidação de tips in-play (mercados ft/1h/2h) para post-mortem."""
from __future__ import annotations

import re

from models.wc_handicap_score import (
    _european_covers,
    _period_goals,
    parse_period_handicap_market,
)

_OVER_RE = re.compile(r"^(ft|1h|2h)_over_(\d+(?:_\d+)?)$")


def _line_from_suffix(suffix: str) -> float:
    return float(suffix.replace("_", "."))


def evaluate_inplay_tip(
    market: str,
    outcome: str,
    *,
    home_score: int,
    away_score: int,
    ht_home: int | None = None,
    ht_away: int | None = None,
    minute: int = 90,
) -> bool | None:
    """Retorna True/False se ganhou/perdeu; None se mercado não avaliável."""
    market = (market or "").strip().lower()
    outcome = (outcome or "").strip().lower()
    ht_h = ht_home if ht_home is not None else home_score
    ht_a = ht_away if ht_away is not None else away_score

    parsed_hcap = parse_period_handicap_market(market)
    if parsed_hcap:
        period, side, line = parsed_hcap
        if outcome not in ("yes", "1", "home"):
            return None
        side_g, opp_g, _ = _period_goals(
            period,
            side,
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            ht_home=ht_h,
            ht_away=ht_a,
        )
        return _european_covers(side_g, opp_g, line, side)

    if market.endswith("_h2h") or market == "h2h":
        period = "ft"
        if market.startswith("1h_"):
            period = "1h"
        elif market.startswith("2h_"):
            period = "2h"
        if period == "1h":
            h, a = ht_h, ht_a
        elif period == "2h":
            h, a = max(0, home_score - ht_h), max(0, away_score - ht_a)
        else:
            h, a = home_score, away_score
        if outcome in ("1", "home"):
            return h > a
        if outcome in ("2", "away"):
            return a > h
        if outcome in ("x", "draw", "0"):
            return h == a
        return None

    over_match = _OVER_RE.match(market)
    if over_match:
        period, line_key = over_match.groups()
        line = _line_from_suffix(line_key)
        if period == "1h":
            total = ht_h + ht_a
        elif period == "2h":
            total = max(0, home_score - ht_h) + max(0, away_score - ht_a)
        else:
            total = home_score + away_score
        if outcome == "yes":
            return total > line
        if outcome == "no":
            return total < line
        return None

    if market == "h2h":
        if outcome in ("1", "home"):
            return home_score > away_score
        if outcome in ("2", "away"):
            return away_score > home_score
        if outcome in ("x", "draw", "0"):
            return home_score == away_score

    if market.startswith("over_") and outcome in ("yes", "no"):
        line = _line_from_suffix(market.replace("over_", ""))
        total = home_score + away_score
        return total > line if outcome == "yes" else total < line

    if market == "btts":
        both = home_score > 0 and away_score > 0
        return both if outcome == "yes" else not both

    return None
