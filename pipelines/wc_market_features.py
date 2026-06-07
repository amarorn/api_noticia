"""Probabilidades implícitas de odds (mercado) para confrontos WC."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from schemas.national_teams import normalize_national_team

DEFAULT_ODDS = Path("data/rounds/wc_2026_odds.json")
DEFAULT_SUPERBET_ODDS = Path("data/rounds/superbet_odds.json")
NEUTRAL = {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3}


def implied_probs_from_odds(odds: dict[str, float]) -> dict[str, float]:
    raw = {k: 1.0 / max(float(odds[k]), 1.01) for k in ("1", "X", "2") if k in odds}
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


def _index_from_odds_file(p: Path) -> dict[str, dict[str, float]]:
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    index: dict[str, dict[str, float]] = {}
    for match in data.get("matches", []):
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        implied = match.get("implied")
        if isinstance(implied, dict) and implied:
            probs = {k: float(implied[k]) for k in ("1", "X", "2") if k in implied}
        else:
            odds = match.get("odds") or {}
            if not odds:
                continue
            probs = implied_probs_from_odds(odds)
        key = f"{home.casefold()}|{away.casefold()}"
        index[key] = probs
    return index


@lru_cache(maxsize=1)
def load_match_odds_index(path: str | None = None) -> dict[str, dict[str, float]]:
    index = _index_from_odds_file(Path(path) if path else DEFAULT_ODDS)
    superbet = _index_from_odds_file(DEFAULT_SUPERBET_ODDS)
    if superbet:
        index.update(superbet)
    return index


def match_implied_probs(home_team: str, away_team: str) -> dict[str, float]:
    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    key = f"{home.casefold()}|{away.casefold()}"
    return load_match_odds_index().get(key, dict(NEUTRAL))


def market_feature_vector(home_team: str, away_team: str) -> list[float]:
    implied = match_implied_probs(home_team, away_team)
    has_market = 1.0 if key_exists(home_team, away_team) else 0.0
    return [
        implied["1"] - implied["2"],
        implied["X"],
        has_market,
    ]


def key_exists(home_team: str, away_team: str) -> bool:
    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    key = f"{home.casefold()}|{away.casefold()}"
    return key in load_match_odds_index()


MARKET_FEATURE_NAMES = [
    "market_implied_12_diff",
    "market_implied_draw",
    "market_odds_available",
]
