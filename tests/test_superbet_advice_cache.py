"""Cache de advice ao vivo — fallback stale por evento."""
from __future__ import annotations

from ingest.superbet.live_advice_cache import (
    advice_cache_key,
    get_stale_advice_for_event,
    set_cached_advice,
)


def test_get_stale_advice_for_event_returns_last_payload():
    key = advice_cache_key(
        event_id=12516174,
        home_score=0,
        away_score=1,
        minute=35,
        bankroll=1000.0,
        fast=True,
        phase="group",
    )
    payload = {"superbet_event_id": 12516174, "minute": 35, "aportes": []}
    set_cached_advice(key, payload, ttl_sec=5.0)

    stale = get_stale_advice_for_event(12516174)
    assert stale is not None
    assert stale["minute"] == 35
    assert stale is not payload
