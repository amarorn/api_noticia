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


__all__ = ["before_date_for_match", "match_is_played", "parse_match_kickoff"]
