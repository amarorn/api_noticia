"""Testes do cache de advice ao vivo."""
from __future__ import annotations

import threading
import time

from ingest.superbet.live_advice_cache import (
    advice_cache_key,
    get_cached_advice,
    run_with_advice_cache,
    set_cached_advice,
)


def test_advice_cache_key_stable():
    key = advice_cache_key(
        event_id=123,
        home_score=1,
        away_score=0,
        minute=45,
        bankroll=1000.0,
        fast=True,
        phase="friendly",
    )
    assert key == (123, 1, 0, 45, 100000, True, "friendly", "national")


def test_run_with_advice_cache_deduplicates_parallel_calls():
    key = advice_cache_key(
        event_id=999,
        home_score=0,
        away_score=0,
        minute=10,
        bankroll=500.0,
        fast=True,
        phase="friendly",
    )
    calls: list[int] = []
    started = threading.Event()

    def compute() -> dict[str, str]:
        calls.append(1)
        started.set()
        time.sleep(0.15)
        return {"ok": "1"}

    results: list[dict[str, str]] = []

    def worker() -> None:
        results.append(run_with_advice_cache(key, compute, fast=True))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    started.wait(timeout=2)
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert len(calls) == 1
    assert len(results) == 2
    assert results[0] == {"ok": "1"}
    assert results[1] == {"ok": "1"}


def test_cached_advice_expires():
    key = (1, 0, 0, 0, 100000, True, "friendly", "national")
    set_cached_advice(key, {"v": 1}, ttl_sec=0.05)
    assert get_cached_advice(key) == {"v": 1}
    time.sleep(0.08)
    assert get_cached_advice(key) is None
