"""Utilitários de predição WC sem vazamento temporal."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def parse_match_kickoff(match: dict[str, Any]) -> datetime | None:
    """Converte kickoff ISO do calendário para datetime UTC-aware."""
    raw = match.get("kickoff")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except ValueError:
        return None


def match_is_played(match: dict[str, Any]) -> bool:
    """Jogo já tem placar oficial no calendário."""
    hs = match.get("home_score")
    aw = match.get("away_score")
    return hs is not None and aw is not None


def before_date_for_match(match: dict[str, Any], *, now: datetime | None = None) -> datetime | None:
    """Cutoff temporal: kickoff do jogo (pré-apito) ou None se já encerrado."""
    if match_is_played(match):
        return None
    kickoff = parse_match_kickoff(match)
    if kickoff is None:
        return None
    now = now or datetime.now(UTC)
    if kickoff <= now:
        return kickoff
    return kickoff


def resolve_inplay_before_date(
    home: str,
    away: str,
    *,
    kickoff_iso: str | None = None,
    snapshot_utc_date: str | None = None,
    now: datetime | None = None,
) -> datetime:
    """Cutoff temporal do modelo in-play: kickoff oficial (ou apito) até o momento atual."""
    from pipelines.wc_schedule import find_schedule_match

    now = now or datetime.now(UTC)

    for raw in (kickoff_iso,):
        dt = parse_match_kickoff({"kickoff": raw}) if raw else None
        if dt is not None:
            return min(dt, now)

    schedule_match = find_schedule_match(home, away)
    if schedule_match is not None:
        dt = parse_match_kickoff(schedule_match)
        if dt is not None:
            return min(dt, now)

    if snapshot_utc_date:
        dt = parse_match_kickoff({"kickoff": snapshot_utc_date})
        if dt is not None:
            return min(dt, now)

    return now


__all__ = [
    "before_date_for_match",
    "match_is_played",
    "parse_match_kickoff",
    "resolve_inplay_before_date",
]
