"""Registro em memória das últimas capturas Superbet ao vivo (pulso de odds)."""
from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

from config import settings

_MAX_EVENTS = 12
_lock = threading.Lock()
_events: dict[int, dict[str, Any]] = {}


def _parse_captured_at(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def record_from_advice_payload(payload: dict[str, Any], *, superbet_stale: bool = False) -> None:
    """Atualiza o registro a partir do JSON de advice (poll ou GET /advice)."""
    event_id = payload.get("superbet_event_id")
    if event_id is None:
        return
    try:
        event_id_int = int(event_id)
    except (TypeError, ValueError):
        return

    captured_at = payload.get("captured_at")
    if not captured_at:
        captured_at = datetime.now(UTC).isoformat()

    entry = {
        "event_id": event_id_int,
        "home_team": payload.get("home_team"),
        "away_team": payload.get("away_team"),
        "minute": payload.get("minute"),
        "current_score": payload.get("current_score"),
        "captured_at": captured_at,
        "superbet_stale": bool(superbet_stale or payload.get("superbet_stale")),
        "is_live": bool(payload.get("is_live")),
        "h2h_odds": payload.get("h2h_odds"),
        "raw_market_count": payload.get("raw_market_count"),
    }

    with _lock:
        _events[event_id_int] = entry
        if len(_events) > _MAX_EVENTS:
            ordered = sorted(
                _events.items(),
                key=lambda item: _parse_captured_at(item[1].get("captured_at")) or datetime.min.replace(tzinfo=UTC),
            )
            for stale_id, _ in ordered[: len(_events) - _MAX_EVENTS]:
                _events.pop(stale_id, None)


def get_superbet_pulse_summary() -> dict[str, Any]:
    """Resumo para Data Pulse — última captura, eventos live e primário mais recente."""
    with _lock:
        entries = list(_events.values())

    poll_interval_sec = int(settings.superbet_poll_interval_sec)
    if not entries:
        return {
            "poll_interval_sec": poll_interval_sec,
            "last_capture_at": None,
            "live_events_count": 0,
            "primary_event_id": None,
            "primary_stale": False,
            "events": [],
        }

    def sort_key(item: dict[str, Any]) -> datetime:
        return _parse_captured_at(item.get("captured_at")) or datetime.min.replace(tzinfo=UTC)

    ordered = sorted(entries, key=sort_key, reverse=True)
    primary = ordered[0]
    last_capture_at = primary.get("captured_at")
    live_events_count = sum(1 for item in entries if item.get("is_live"))

    return {
        "poll_interval_sec": poll_interval_sec,
        "last_capture_at": last_capture_at,
        "live_events_count": live_events_count,
        "primary_event_id": primary.get("event_id"),
        "primary_stale": bool(primary.get("superbet_stale")),
        "events": ordered[:8],
    }


def reset_superbet_pulse_registry() -> None:
    """Limpa o registro — útil em testes."""
    with _lock:
        _events.clear()


__all__ = [
    "get_superbet_pulse_summary",
    "record_from_advice_payload",
    "reset_superbet_pulse_registry",
]
