from __future__ import annotations

import re
from typing import Any

STAT_KEY_ALIASES: dict[str, str] = {
    "ballpossession": "possession_pct",
    "cornerkicks": "corners",
    "totalshots": "shots_total",
    "shotsontarget": "shots_on_target",
    "shotsofftarget": "shots_off_target",
    "blockedshots": "blocked_shots",
    "expectedgoals": "xg",
    "fouls": "fouls",
    "yellowcards": "yellow_cards",
    "redcards": "red_cards",
    "offsides": "offsides",
    "bigchances": "big_chances",
    "passes": "passes",
    "accuratepasses": "passes_accurate",
    "duelswon": "duels_won",
    "aerialduelswon": "aerial_duels_won",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "goalkeeper saves": "gk_saves",
    "goalkeepersaves": "gk_saves",
}

STAT_NAME_ALIASES: dict[str, str] = {
    "ball possession": "possession_pct",
    "corner kicks": "corners",
    "total shots": "shots_total",
    "shots on target": "shots_on_target",
    "shots off target": "shots_off_target",
    "blocked shots": "blocked_shots",
    "expected goals": "xg",
    "fouls": "fouls",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "offsides": "offsides",
    "big chances": "big_chances",
    "passes": "passes",
    "accurate passes": "passes_accurate",
    "duels won": "duels_won",
    "aerial duels won": "aerial_duels_won",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "goalkeeper saves": "gk_saves",
}


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _resolve_stat_key(item: dict[str, Any]) -> str | None:
    raw_key = item.get("key")
    if isinstance(raw_key, str) and raw_key.strip():
        token = _normalize_token(raw_key)
        if token in STAT_KEY_ALIASES:
            return STAT_KEY_ALIASES[token]

    name = str(item.get("name") or "").strip().lower()
    if name in STAT_NAME_ALIASES:
        return STAT_NAME_ALIASES[name]
    token = _normalize_token(name)
    return STAT_KEY_ALIASES.get(token)


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _side_values(item: dict[str, Any]) -> tuple[float | None, float | None]:
    home = _parse_numeric(item.get("homeValue"))
    away = _parse_numeric(item.get("awayValue"))
    if home is None:
        home = _parse_numeric(item.get("home"))
    if away is None:
        away = _parse_numeric(item.get("away"))
    if home is None:
        home = _parse_numeric(item.get("homeTotal"))
    if away is None:
        away = _parse_numeric(item.get("awayTotal"))
    return home, away


def map_event_statistics(payload: dict[str, Any]) -> dict[str, float | int | None]:
    """Achata statisticsItems do Sofascore em home_* / away_*."""
    out: dict[str, float | int | None] = {}
    periods = payload.get("statistics") or []
    if not periods:
        return out

    all_period = next(
        (block for block in periods if str(block.get("period") or "").upper() == "ALL"),
        periods[0],
    )
    for group in all_period.get("groups") or []:
        for item in group.get("statisticsItems") or []:
            metric = _resolve_stat_key(item)
            if not metric:
                continue
            home, away = _side_values(item)
            out[f"home_{metric}"] = home
            out[f"away_{metric}"] = away
    return out


def map_event_incidents(payload: dict[str, Any]) -> dict[str, int]:
    """Resume cartões e gols a partir da timeline de incidentes."""
    counts = {
        "incident_goals_home": 0,
        "incident_goals_away": 0,
        "incident_yellow_cards_home": 0,
        "incident_yellow_cards_away": 0,
        "incident_red_cards_home": 0,
        "incident_red_cards_away": 0,
        "incident_substitutions_home": 0,
        "incident_substitutions_away": 0,
    }
    for item in payload.get("incidents") or []:
        is_home = bool(item.get("isHome"))
        side = "home" if is_home else "away"
        incident_type = str(item.get("incidentType") or "").lower()
        incident_class = str(item.get("incidentClass") or "").lower()

        if incident_type == "goal":
            counts[f"incident_goals_{side}"] += 1
        elif incident_type == "card":
            if incident_class == "red":
                counts[f"incident_red_cards_{side}"] += 1
            else:
                counts[f"incident_yellow_cards_{side}"] += 1
        elif incident_type == "substitution":
            counts[f"incident_substitutions_{side}"] += 1

    return counts


def flatten_match_stats(
    *,
    event_id: int,
    home_team: str,
    away_team: str,
    match_date: str | None,
    statistics_payload: dict[str, Any] | None,
    incidents_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "match_date": match_date,
        "source": "sofascore",
    }
    if statistics_payload:
        row.update(map_event_statistics(statistics_payload))
    if incidents_payload:
        row.update(map_event_incidents(incidents_payload))
    return row
