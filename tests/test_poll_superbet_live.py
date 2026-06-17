"""Poll Superbet ao vivo — resiliência e resolução de event_ids."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ingest.superbet.client import SuperbetClientError
from pipelines.poll_superbet_live import (
    _resolve_event_ids,
    _resolve_event_ids_resilient,
    poll_loop,
)


def test_resolve_event_ids_skips_api_when_ids_fixed():
    client = MagicMock()
    ids = _resolve_event_ids(
        client,
        event_ids=[12516174],
        auto=True,
        sport_id=5,
    )
    assert ids == [12516174]
    client.fetch_live_events.assert_not_called()


def test_resolve_event_ids_resilient_reuses_last_auto_ids():
    client = MagicMock()
    client.fetch_live_events.side_effect = SuperbetClientError("dns fail")

    ids, cached = _resolve_event_ids_resilient(
        client,
        event_ids=None,
        auto=True,
        sport_id=5,
        last_auto_ids=[12516174],
    )
    assert ids == [12516174]
    assert cached == [12516174]


def test_resolve_event_ids_resilient_updates_cache_on_success():
    client = MagicMock()
    summary = MagicMock(event_id=12516174, home_team="Iraque", away_team="Noruega")
    client.fetch_live_events.return_value = [summary]

    ids, cached = _resolve_event_ids_resilient(
        client,
        event_ids=None,
        auto=True,
        sport_id=5,
        filter_international=False,
        last_auto_ids=None,
    )
    assert ids == [12516174]
    assert cached == [12516174]


def test_poll_loop_survives_superbet_outage(monkeypatch):
    calls = {"n": 0}

    def fake_resolve(*_args, **_kwargs):
        calls["n"] += 1
        return [12516174], [12516174]

    monkeypatch.setattr(
        "pipelines.poll_superbet_live.load_or_train_wc_predictor",
        lambda **_: (object(), {}),
    )
    monkeypatch.setattr(
        "pipelines.poll_superbet_live._resolve_event_ids_resilient",
        fake_resolve,
    )
    monkeypatch.setattr(
        "pipelines.poll_superbet_live.poll_once",
        lambda *_a, **_k: {"captured": 1, "skipped": 0, "errors": 0},
    )
    monkeypatch.setattr("pipelines.poll_superbet_live.time.sleep", lambda _sec: None)

    rc = poll_loop(None, auto=True, interval_sec=1, allow_train=False, max_cycles=2)
    assert rc == 0
    assert calls["n"] == 2
