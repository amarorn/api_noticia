"""Cache em memória para respostas de advice ao vivo (evita recomputar Poisson a cada poll)."""
from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from config import settings

T = TypeVar("T")

_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
_EVENT_LATEST: dict[int, tuple[float, dict[str, Any]]] = {}
_INFLIGHT: dict[tuple[Any, ...], tuple[threading.Event, dict[str, Any] | None, BaseException | None]] = {}
_LOCK = threading.Lock()

_DEFAULT_TTL_FAST = 8.0
_DEFAULT_TTL_FULL = 12.0


def advice_cache_key(
    *,
    event_id: int,
    home_score: int,
    away_score: int,
    minute: int,
    bankroll: float,
    fast: bool,
    phase: str,
    match_kind: str = "national",
) -> tuple[Any, ...]:
    return (
        event_id,
        home_score,
        away_score,
        minute,
        int(bankroll * 100),
        fast,
        phase,
        match_kind,
    )


def _get_cached_unlocked(key: tuple[Any, ...]) -> dict[str, Any] | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, payload = entry
    if time.monotonic() > expires_at:
        del _CACHE[key]
        return None
    return payload


def get_cached_advice(key: tuple[Any, ...]) -> dict[str, Any] | None:
    with _LOCK:
        return _get_cached_unlocked(key)


def set_cached_advice(key: tuple[Any, ...], payload: dict[str, Any], *, ttl_sec: float) -> None:
    with _LOCK:
        _CACHE[key] = (time.monotonic() + ttl_sec, payload)
        event_id = key[0]
        if isinstance(event_id, int):
            stale_ttl = max(ttl_sec, float(settings.superbet_stale_max_age_sec))
            _EVENT_LATEST[event_id] = (
                time.monotonic() + stale_ttl,
                copy.deepcopy(payload),
            )


def get_stale_advice_for_event(
    event_id: int,
    *,
    max_age_sec: float | None = None,
) -> dict[str, Any] | None:
    """Última resposta de advice conhecida para o evento (fallback offline)."""
    with _LOCK:
        entry = _EVENT_LATEST.get(event_id)
        if entry is None:
            return None
        expires_at, payload = entry
        now = time.monotonic()
        if max_age_sec is not None:
            max_expires = now + float(max_age_sec)
            if expires_at > max_expires:
                expires_at = max_expires
        if now > expires_at:
            if _EVENT_LATEST.get(event_id) == entry:
                del _EVENT_LATEST[event_id]
            return None
        return copy.deepcopy(payload)


def run_with_advice_cache(
    key: tuple[Any, ...],
    compute: Callable[[], T],
    *,
    fast: bool,
) -> T:
    """Retorna cache hit, deduplica requests paralelos ou executa ``compute``."""
    cached = get_cached_advice(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    ttl = _DEFAULT_TTL_FAST if fast else _DEFAULT_TTL_FULL

    with _LOCK:
        cached = _get_cached_unlocked(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        inflight = _INFLIGHT.get(key)
        if inflight is None:
            wait_event = threading.Event()
            _INFLIGHT[key] = (wait_event, None, None)
            is_leader = True
        else:
            wait_event, _, _ = inflight
            is_leader = False

    if not is_leader:
        wait_event.wait(timeout=120.0)
        with _LOCK:
            inflight = _INFLIGHT.get(key)
            if inflight is not None:
                _, result, error = inflight
                if error is not None:
                    raise error
                if result is not None:
                    return result  # type: ignore[return-value]
        cached = get_cached_advice(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        return run_with_advice_cache(key, compute, fast=fast)

    try:
        result = compute()
        if isinstance(result, dict):
            set_cached_advice(key, result, ttl_sec=ttl)
        with _LOCK:
            inflight = _INFLIGHT.get(key)
            if inflight is not None:
                event, _, err = inflight
                _INFLIGHT[key] = (event, result if isinstance(result, dict) else None, err)
        return result
    except BaseException as exc:
        with _LOCK:
            inflight = _INFLIGHT.get(key)
            if inflight is not None:
                event, res, _ = inflight
                _INFLIGHT[key] = (event, res, exc)
        raise
    finally:
        with _LOCK:
            inflight = _INFLIGHT.pop(key, None)
        if inflight is not None:
            inflight[0].set()


def list_cached_event_ids(*, max_age_sec: float | None = None) -> list[int]:
    """Retorna IDs de todos os eventos com advice em cache (não expirado)."""
    now = time.monotonic()
    with _LOCK:
        result = []
        for event_id, (expires_at, _) in _EVENT_LATEST.items():
            if max_age_sec is not None:
                cutoff = now + float(max_age_sec)
                if expires_at > cutoff:
                    continue
            if now <= expires_at:
                result.append(event_id)
        return result


__all__ = [
    "advice_cache_key",
    "get_cached_advice",
    "get_stale_advice_for_event",
    "list_cached_event_ids",
    "run_with_advice_cache",
    "set_cached_advice",
]
