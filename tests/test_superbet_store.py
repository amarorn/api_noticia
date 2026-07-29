"""Persistência e fallback bronze Superbet."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from ingest.superbet.client import SuperbetClientError
from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
from ingest.superbet.store import (
    fetch_event_with_stale_fallback,
    is_valid_superbet_event_id,
    load_latest_snapshot,
    save_event_snapshot,
)


def _sample_snapshot(event_id: int = 12516174) -> SuperbetEventSnapshot:
    return SuperbetEventSnapshot(
        event_id=event_id,
        home_team="Iraque",
        away_team="Noruega",
        event_name="Iraque·Noruega",
        utc_date="2026-06-16T19:00:00Z",
        betradar_id="br:123",
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=0,
            away_score=1,
            minute=35,
            stoppage_time=None,
            home_corners=2,
            away_corners=1,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="1T",
            status="LIVE",
        ),
        h2h_odds={"1": 4.5, "X": 3.2, "2": 1.9},
        h2h_implied={"1": 0.2, "X": 0.28, "2": 0.52},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        raw_market_count=8,
        captured_at="2026-06-16T20:35:00Z",
    )


def test_fetch_event_with_stale_fallback_uses_bronze(tmp_path, monkeypatch):
    monkeypatch.setattr("ingest.superbet.store.settings.lake_root", tmp_path)
    snapshot = _sample_snapshot()
    save_event_snapshot(snapshot)

    client = MagicMock()
    client.fetch_event.side_effect = SuperbetClientError("dns fail")

    loaded, stale = fetch_event_with_stale_fallback(client, snapshot.event_id)
    assert stale is True
    assert loaded.event_id == snapshot.event_id
    assert loaded.home_team == "Iraque"
    assert loaded.inplay is not None
    assert loaded.inplay.minute == 35


def test_fetch_event_with_stale_fallback_raises_without_bronze():
    client = MagicMock()
    client.fetch_event.side_effect = SuperbetClientError("dns fail")

    with pytest.raises(SuperbetClientError):
        fetch_event_with_stale_fallback(client, 999999)


def test_fetch_event_with_stale_fallback_rejects_invalid_event_id():
    client = MagicMock()
    with pytest.raises(SuperbetClientError, match="inválido"):
        fetch_event_with_stale_fallback(client, 123)
    client.fetch_event.assert_not_called()


def test_is_valid_superbet_event_id_respects_minimum(monkeypatch):
    monkeypatch.setattr("ingest.superbet.store.settings.superbet_min_event_id", 1_000_000)
    assert is_valid_superbet_event_id(1_000_000) is True
    assert is_valid_superbet_event_id(12_512_380) is True
    assert is_valid_superbet_event_id(123) is False
    assert is_valid_superbet_event_id(777) is False


def test_load_latest_snapshot_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("ingest.superbet.store.settings.lake_root", tmp_path)
    snapshot = _sample_snapshot(777)
    save_event_snapshot(snapshot)

    latest_path = tmp_path / "bronze" / "superbet" / "events" / "777" / "latest.json"
    assert latest_path.exists()
    data = json.loads(latest_path.read_text(encoding="utf-8"))
    assert data["home_team"] == "Iraque"

    loaded = load_latest_snapshot(777)
    assert loaded is not None
    assert loaded.event_id == 777
