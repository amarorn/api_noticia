from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from ingest.fifa.match_ingest import load_fifa_window_matches
from ingest.fifa.teams import fifa_country_code
from ingest.sofascore.friendlies import FriendlyMatch, match_year
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


def _extract_name(names: list[dict] | None) -> str:
    if not names:
        return ""
    for item in names:
        if str(item.get("Locale", "")).lower().startswith("pt"):
            return str(item.get("Description") or "")
    return str(names[0].get("Description") or "")


def is_fifa_friendly_match(match: dict[str, Any]) -> bool:
    for season in match.get("SeasonName") or []:
        text = str(season.get("Description") or "").lower()
        if "friendly" in text or "amistoso" in text:
            return True
    competition = match.get("CompetitionName")
    if isinstance(competition, list):
        text = _extract_name(competition).lower()
        return "friendly" in text or "amistoso" in text
    return False


def _fifa_match_status(match: dict[str, Any]) -> str:
    period = int(match.get("Period") or 0)
    if period >= 10:
        return "finished"
    if period > 0:
        return "live"
    return "notstarted"


def _fifa_team_name(side: dict[str, Any]) -> str:
    names = side.get("TeamName") or []
    raw = _extract_name(names)
    return normalize_national_team(raw) if raw else ""


def map_fifa_window_match(
    match: dict[str, Any],
    *,
    team: str,
) -> FriendlyMatch | None:
    if not is_fifa_friendly_match(match):
        return None

    canonical = normalize_national_team(team)
    home_side = match.get("Home") or match.get("HomeTeam") or {}
    away_side = match.get("Away") or match.get("AwayTeam") or {}
    home = _fifa_team_name(home_side)
    away = _fifa_team_name(away_side)
    if canonical not in {home, away}:
        return None

    date_raw = str(match.get("Date") or "")
    tournament = _extract_name(match.get("SeasonName")) or "Friendly"

    return FriendlyMatch(
        event_id=None,
        fifa_match_id=str(match.get("IdMatch") or ""),
        home_team=home,
        away_team=away,
        match_date=date_raw or None,
        status=_fifa_match_status(match),
        home_score=_safe_int(match.get("HomeTeamScore")),
        away_score=_safe_int(match.get("AwayTeamScore")),
        tournament=tournament,
        is_home=canonical == home,
        sources=("fifa",),
    )


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def list_fifa_team_friendlies(
    team: str,
    *,
    year: int | None = None,
    matches: list[dict[str, Any]] | None = None,
) -> list[FriendlyMatch]:
    filter_year = year if year is not None else datetime.now(timezone.utc).year
    code = fifa_country_code(team)
    if not code:
        return []

    if matches is not None:
        window = matches
    else:
        try:
            window = load_fifa_window_matches()
        except Exception as exc:
            logger.warning("fifa_friendlies_window_unavailable", team=team, error=str(exc))
            return []
    seen: set[str] = set()
    rows: list[FriendlyMatch] = []

    for raw in window:
        home_code = str((raw.get("Home") or raw.get("HomeTeam") or {}).get("IdCountry") or "")
        away_code = str((raw.get("Away") or raw.get("AwayTeam") or {}).get("IdCountry") or "")
        if code not in {home_code, away_code}:
            continue

        mapped = map_fifa_window_match(raw, team=team)
        if mapped is None:
            continue
        if match_year(mapped.match_date) != filter_year:
            continue

        fifa_id = mapped.fifa_match_id or ""
        if fifa_id in seen:
            continue
        seen.add(fifa_id)
        rows.append(mapped)

    rows.sort(key=lambda item: item.match_date or "", reverse=True)
    return rows
