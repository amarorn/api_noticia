"""Cache TTL para respostas do copiloto GPT ao vivo."""
from __future__ import annotations

import copy
import threading
import time
from typing import Any

_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_EVENT_LATEST: dict[int, tuple[float, dict[str, Any]]] = {}
_LOCK = threading.Lock()


def get_cached_copilot(key: tuple[Any, ...]) -> dict[str, Any] | None:
    with _LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if time.monotonic() > expires_at:
            del _CACHE[key]
            return None
        return copy.deepcopy(payload)


def set_cached_copilot(key: tuple[Any, ...], payload: dict[str, Any], *, ttl_sec: float) -> None:
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl_sec, copy.deepcopy(payload))
        if len(key) >= 2 and isinstance(key[1], int):
            stale_ttl = max(ttl_sec, 60.0)
            _EVENT_LATEST[key[1]] = (time.monotonic() + stale_ttl, copy.deepcopy(payload))


def get_stale_copilot_for_event(
    event_id: int,
    *,
    max_age_sec: float | None = None,
) -> dict[str, Any] | None:
    """Última resposta do copiloto para o evento (fallback rápido no endpoint)."""
    with _LOCK:
        entry = _EVENT_LATEST.get(event_id)
        if entry is None:
            return None
        expires_at, payload = entry
        now = time.monotonic()
        if max_age_sec is not None and now + float(max_age_sec) < expires_at:
            expires_at = now + float(max_age_sec)
        if now > expires_at:
            del _EVENT_LATEST[event_id]
            return None
        return copy.deepcopy(payload)


__all__ = ["get_cached_copilot", "get_stale_copilot_for_event", "set_cached_copilot"]
