"""Testes de finalização automática de eventos Superbet."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ingest.superbet.event_finalize import (
    is_event_finalized,
    list_pending_watch_event_ids,
    mark_event_watchlist_discarded,
    maybe_finalize_finished_event,
    save_finished_event_record,
    sweep_stale_watchlist_events,
    try_finalize_from_bronze,
)


@pytest.fixture
def mock_snapshot():
    ip = MagicMock()
    ip.home_score = 2
    ip.away_score = 1
    ip.ht_home_score = 1
    ip.ht_away_score = 0
    ip.minute = 90
    ip.home_corners = 4
    ip.away_corners = 3
    ip.status = "FINISHED"
    ip.period_label = "2T"
    snap = MagicMock()
    snap.event_id = 12512380
    snap.home_team = "Coreia do Sul"
    snap.away_team = "República Tcheca"
    snap.betradar_id = "br-1"
    snap.captured_at = "2026-06-11T23:00:00Z"
    snap.inplay = ip
    snap.h2h_odds = {"1": 2.1, "X": 3.2, "2": 3.5}
    return snap


def test_save_finished_event_record(tmp_path, mock_snapshot):
    with patch("ingest.superbet.event_finalize.settings") as mock_settings:
        mock_settings.lake_root = tmp_path / "lake"
        mock_settings.gold_path = tmp_path / "lake" / "gold"
        mock_settings.bronze_path = tmp_path / "lake" / "bronze"

        path = save_finished_event_record(
            event_id=12512380,
            snapshot=mock_snapshot,
            inplay={"current_score": "2x1", "prob_final_home": 0.5},
            advice={"aportes": [], "confidence": {"score": 0.6}},
        )
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["final_score"] == "2x1"
        assert data["event_id"] == 12512380


def test_finalize_idempotent(tmp_path, mock_snapshot):
    with (
        patch("ingest.superbet.event_finalize.settings") as mock_settings,
        patch("ingest.superbet.event_finalize.merge_snapshot_into_odds_file") as merge,
        patch("ingest.superbet.event_finalize._enqueue_retrain") as enqueue,
    ):
        mock_settings.lake_root = tmp_path / "lake"
        mock_settings.gold_path = tmp_path / "lake" / "gold"
        mock_settings.bronze_path = tmp_path / "lake" / "bronze"
        mock_settings.superbet_finalize_enabled = True
        mock_settings.superbet_finalize_retrain = True

        merge.return_value = tmp_path / "odds.json"
        inplay = {"current_score": "2x1"}
        advice = {"aportes": []}

        first = maybe_finalize_finished_event(
            event_id=12512380,
            snapshot=mock_snapshot,
            inplay=inplay,
            advice=advice,
            is_finished=True,
        )
        second = maybe_finalize_finished_event(
            event_id=12512380,
            snapshot=mock_snapshot,
            inplay=inplay,
            advice=advice,
            is_finished=True,
        )

        assert first is not None
        assert second is not None
        assert is_event_finalized(12512380)
        enqueue.assert_called_once()


def test_finalize_settles_open_bets(tmp_path, mock_snapshot):
    with (
        patch("ingest.superbet.event_finalize.settings") as mock_settings,
        patch("ingest.superbet.event_finalize.merge_snapshot_into_odds_file") as merge,
        patch("ingest.superbet.event_finalize._enqueue_retrain"),
        patch("models.open_bet_settle.settle_open_bets_for_event") as settle,
    ):
        mock_settings.lake_root = tmp_path / "lake"
        mock_settings.gold_path = tmp_path / "lake" / "gold"
        mock_settings.bronze_path = tmp_path / "lake" / "bronze"
        mock_settings.superbet_finalize_enabled = True
        mock_settings.superbet_finalize_retrain = False
        mock_settings.superbet_finalize_settle_open_bets = True

        merge.return_value = tmp_path / "odds.json"
        settle.return_value = {"settled": 1}

        result = maybe_finalize_finished_event(
            event_id=12512380,
            snapshot=mock_snapshot,
            inplay={"current_score": "2x1"},
            advice={"aportes": []},
            is_finished=True,
        )

        assert result is not None
        settle.assert_called_once_with(
            event_id=12512380,
            home_team="Coreia do Sul",
            away_team="República Tcheca",
            home_score=2,
            away_score=1,
            final_score="2x1",
            home_corners=4,
            away_corners=3,
            baseball_innings=mock_snapshot.inplay.baseball_innings,
        )


def test_list_pending_watch_event_ids_ignora_bronze_de_teste(tmp_path, monkeypatch):
    """Bronze local de testes (event_id=123) não entra na watchlist do poll."""
    monkeypatch.setattr("ingest.superbet.event_finalize.settings.lake_root", tmp_path)
    monkeypatch.setattr("ingest.superbet.event_finalize.settings.superbet_min_event_id", 1_000_000)

    test_dir = tmp_path / "bronze" / "superbet" / "events" / "123"
    test_dir.mkdir(parents=True)
    (test_dir / "latest.json").write_text('{"event_id": 123}', encoding="utf-8")

    real_dir = tmp_path / "bronze" / "superbet" / "events" / "12512380"
    real_dir.mkdir(parents=True)
    (real_dir / "latest.json").write_text('{"event_id": 12512380}', encoding="utf-8")

    pending = list_pending_watch_event_ids()
    assert pending == [12512380]


def test_mark_event_watchlist_discarded(tmp_path):
    with patch("ingest.superbet.event_finalize.settings") as mock_settings:
        mock_settings.lake_root = tmp_path / "lake"
        entry = mark_event_watchlist_discarded(12922333, "api_404")
        assert entry["discarded"] is True
        assert is_event_finalized(12922333)


def test_try_finalize_from_bronze_finished(tmp_path):
    event_id = 12512380
    bronze_dir = tmp_path / "lake" / "bronze" / "superbet" / "events" / str(event_id)
    bronze_dir.mkdir(parents=True)
    (bronze_dir / "latest.json").write_text(
        json.dumps(
            {
                "event_id": event_id,
                "home_team": "A",
                "away_team": "B",
                "is_live": False,
                "inplay": {
                    "status": "FINISHED",
                    "home_score": 3,
                    "away_score": 2,
                    "minute": 9,
                },
            }
        ),
        encoding="utf-8",
    )

    with (
        patch("ingest.superbet.event_finalize.settings") as mock_settings,
        patch("ingest.superbet.event_finalize.merge_snapshot_into_odds_file"),
        patch("ingest.superbet.event_finalize._enqueue_retrain"),
    ):
        mock_settings.lake_root = tmp_path / "lake"
        mock_settings.gold_path = tmp_path / "lake" / "gold"
        mock_settings.bronze_path = tmp_path / "lake" / "bronze"
        mock_settings.superbet_finalize_enabled = True
        mock_settings.superbet_finalize_retrain = False

        from ingest.superbet.store import load_latest_snapshot

        snap = load_latest_snapshot(event_id)
        assert snap is not None

        result = try_finalize_from_bronze(event_id)
        assert result is not None
        assert is_event_finalized(event_id)


def test_sweep_stale_watchlist_discards_old_bronze(tmp_path):
    event_id = 12512380
    snap = MagicMock()
    snap.is_live = False
    ip = MagicMock()
    ip.status = "LIVE"
    snap.inplay = ip

    with (
        patch("ingest.superbet.event_finalize.settings") as mock_settings,
        patch("ingest.superbet.event_finalize.try_finalize_from_bronze", return_value=None),
        patch("ingest.superbet.event_finalize._bronze_latest_age_hours", return_value=13.0),
        patch("ingest.superbet.store.load_latest_snapshot", return_value=snap),
    ):
        mock_settings.lake_root = tmp_path / "lake"
        mock_settings.superbet_watchlist_sweep_enabled = True
        mock_settings.superbet_watchlist_stale_hours = 12.0

        swept = sweep_stale_watchlist_events([event_id], live_event_ids=set())
        assert len(swept) == 1
        assert swept[0]["action"] == "discarded"
        assert is_event_finalized(event_id)
