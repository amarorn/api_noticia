"""Testes de finalização automática de eventos Superbet."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ingest.superbet.event_finalize import (
    is_event_finalized,
    maybe_finalize_finished_event,
    save_finished_event_record,
)


@pytest.fixture
def mock_snapshot():
    ip = MagicMock()
    ip.home_score = 2
    ip.away_score = 1
    ip.ht_home_score = 1
    ip.ht_away_score = 0
    ip.minute = 90
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
        )
