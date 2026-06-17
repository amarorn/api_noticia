"""Testes do registro Superbet no Data Pulse."""
from __future__ import annotations

from api.data_pulse import build_pulse_snapshot, pulse_response_headers
from ingest.superbet.live_pulse_registry import (
    get_superbet_pulse_summary,
    record_from_advice_payload,
    reset_superbet_pulse_registry,
)


def setup_function() -> None:
    reset_superbet_pulse_registry()


def test_record_from_advice_payload_tracks_live_event() -> None:
    record_from_advice_payload(
        {
            "superbet_event_id": 13127506,
            "home_team": "Argentina",
            "away_team": "Argélia",
            "minute": 44,
            "current_score": "1x0",
            "captured_at": "2026-06-15T20:30:00+00:00",
            "is_live": True,
            "h2h_odds": {"1": 1.45, "x": 4.2, "2": 8.5},
            "raw_market_count": 87,
        }
    )

    summary = get_superbet_pulse_summary()
    assert summary["live_events_count"] == 1
    assert summary["primary_event_id"] == 13127506
    assert summary["primary_stale"] is False
    assert summary["last_capture_at"] == "2026-06-15T20:30:00+00:00"
    assert summary["events"][0]["h2h_odds"]["1"] == 1.45


def test_build_pulse_snapshot_includes_superbet_live() -> None:
    record_from_advice_payload(
        {
            "superbet_event_id": 99,
            "home_team": "Brasil",
            "away_team": "Egito",
            "minute": 12,
            "current_score": "0x0",
            "captured_at": "2026-06-15T21:00:00+00:00",
            "is_live": True,
        },
        superbet_stale=True,
    )

    snapshot = build_pulse_snapshot(wc_models_ready=True, force_lake_counts=True)
    superbet = snapshot["superbet_live"]
    assert superbet["primary_event_id"] == 99
    assert superbet["primary_stale"] is True

    headers = pulse_response_headers(snapshot)
    assert headers["X-Superbet-Last-Capture-At"] == "2026-06-15T21:00:00+00:00"
    assert headers["X-Superbet-Live-Events"] == "1"
    assert headers["X-Superbet-Stale"] == "true"
    assert headers["X-Superbet-Primary-Event-Id"] == "99"
    assert int(headers["X-Superbet-Poll-Interval-Sec"]) > 0


def test_empty_superbet_pulse_defaults() -> None:
    summary = get_superbet_pulse_summary()
    assert summary["live_events_count"] == 0
    assert summary["primary_event_id"] is None

    snapshot = build_pulse_snapshot(wc_models_ready=False, force_lake_counts=True)
    headers = pulse_response_headers(snapshot)
    assert headers["X-Superbet-Last-Capture-At"] == ""
    assert headers["X-Superbet-Live-Events"] == "0"
    assert headers["X-Superbet-Stale"] == "false"
