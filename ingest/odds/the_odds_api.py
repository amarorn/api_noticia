from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import json

from config import settings
from schemas.national_teams import normalize_national_team

ODDS_API_BASE = "https://api.the-odds-api.com/v4"


@dataclass
class H2HOdds:
    home_team: str
    away_team: str
    odds_1: float
    odds_x: float
    odds_2: float
    bookmaker: str
    commence_time: str | None = None


def _event_key(home_team: str, away_team: str) -> frozenset[str]:
    return frozenset(
        {
            normalize_national_team(home_team),
            normalize_national_team(away_team),
        }
    )


def _map_outcomes(outcomes: list[dict], home_team: str, away_team: str) -> dict[str, float]:
    mapped: dict[str, float] = {}
    home_norm = normalize_national_team(home_team)
    away_norm = normalize_national_team(away_team)

    for item in outcomes:
        name = str(item.get("name", "")).strip()
        price = item.get("price")
        if not isinstance(price, (float, int)):
            continue
        odd = float(price)
        if odd <= 1.0:
            continue

        normalized = normalize_national_team(name)
        name_lower = name.lower()
        if normalized == home_norm:
            mapped["1"] = odd
        elif normalized == away_norm:
            mapped["2"] = odd
        elif name_lower in {"draw", "tie", "empate", "x"}:
            mapped["X"] = odd

    return mapped


def _extract_h2h(event: dict, preferred_bookmaker: str | None = None) -> H2HOdds | None:
    home = str(event.get("home_team", "")).strip()
    away = str(event.get("away_team", "")).strip()
    if not home or not away:
        return None

    bookmakers = event.get("bookmakers") or []
    if not isinstance(bookmakers, list) or not bookmakers:
        return None

    if preferred_bookmaker:
        pref = preferred_bookmaker.lower()
        matching = [b for b in bookmakers if str(b.get("key", "")).lower() == pref]
        if matching:
            bookmakers = matching

    for bookmaker in bookmakers:
        markets = bookmaker.get("markets") or []
        for market in markets:
            if market.get("key") != "h2h":
                continue
            outcomes = market.get("outcomes") or []
            mapped = _map_outcomes(outcomes, home, away)
            if {"1", "X", "2"}.issubset(mapped):
                return H2HOdds(
                    home_team=normalize_national_team(home),
                    away_team=normalize_national_team(away),
                    odds_1=mapped["1"],
                    odds_x=mapped["X"],
                    odds_2=mapped["2"],
                    bookmaker=str(bookmaker.get("key", "unknown")),
                    commence_time=event.get("commence_time"),
                )
    return None


def fetch_live_h2h_odds(
    *,
    sport_key: str | None = None,
    regions: str | None = None,
    markets: str | None = None,
    odds_format: str | None = None,
    preferred_bookmaker: str | None = None,
) -> list[H2HOdds]:
    api_key = settings.odds_api_key
    if not api_key:
        raise ValueError("ODDS_API_KEY não configurada no .env")

    sport = sport_key or settings.odds_default_sport
    params = {
        "apiKey": api_key,
        "regions": regions or settings.odds_default_regions,
        "markets": markets or settings.odds_default_markets,
        "oddsFormat": odds_format or settings.odds_default_odds_format,
    }
    url = f"{ODDS_API_BASE}/sports/{sport}/odds"

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, list):
        raise ValueError("Resposta inesperada da Odds API")

    extracted: list[H2HOdds] = []
    for event in payload:
        if not isinstance(event, dict):
            continue
        h2h = _extract_h2h(event, preferred_bookmaker=preferred_bookmaker)
        if h2h:
            extracted.append(h2h)

    return extracted


def merge_schedule_with_odds(
    schedule: dict,
    live_odds: list[H2HOdds],
) -> tuple[dict, int]:
    index: dict[frozenset[str], H2HOdds] = {
        _event_key(item.home_team, item.away_team): item for item in live_odds
    }
    phase = schedule.get("phase", "group")
    output_matches: list[dict] = []
    matched = 0

    for match in schedule.get("matches", []):
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        key = _event_key(home, away)
        entry = index.get(key)
        if not entry:
            continue
        matched += 1
        output_matches.append(
            {
                "home_team": home,
                "away_team": away,
                "phase": match.get("phase", phase),
                "group": match.get("group"),
                "bookmaker": entry.bookmaker,
                "commence_time": entry.commence_time,
                "odds": {
                    "1": round(entry.odds_1, 3),
                    "X": round(entry.odds_x, 3),
                    "2": round(entry.odds_2, 3),
                },
            }
        )

    output = {
        "season": schedule.get("season"),
        "competition": schedule.get("competition"),
        "phase": phase,
        "round": schedule.get("round"),
        "source": "the-odds-api",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "matches": output_matches,
    }
    return output, matched


def save_odds_file(data: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
