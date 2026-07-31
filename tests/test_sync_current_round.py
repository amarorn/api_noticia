"""Testes sync-current-round e resolve_club_competition."""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from ingest.superbet.team_resolver import resolve_club_competition
from pipelines.sync_current_round import build_round_schedule, sync_current_round


def test_resolve_club_competition():
    assert resolve_club_competition("Flamengo", "Palmeiras") == "Brasileirão"
    assert resolve_club_competition("Flamengo", "River Plate") == "Copa Libertadores"
    assert resolve_club_competition("Arsenal", "Chelsea") == ""


def test_build_round_schedule(tmp_path, monkeypatch):
    import pipelines.sync_current_round as sync_mod

    df = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "season": 2025,
                "competition": "Brasileirão",
                "round_number": 10,
                "home_team": "Flamengo",
                "away_team": "Palmeiras",
                "home_score": None,
                "away_score": None,
                "match_date": datetime(2025, 6, 1, tzinfo=UTC),
                "label": None,
            }
        ]
    )
    monkeypatch.setattr(sync_mod, "load_fixtures", lambda **kwargs: df)

    schedule = build_round_schedule(2025, 10, competition_key="brasileirao")
    assert schedule["round"] == 10
    assert len(schedule["matches"]) == 1
    assert schedule["matches"][0]["home_team"] == "Flamengo"


def test_sync_current_round_writes_json(tmp_path, monkeypatch):
    import pipelines.sync_current_round as sync_mod

    df = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "season": 2025,
                "competition": "Brasileirão",
                "round_number": 1,
                "home_team": "Flamengo",
                "away_team": "Botafogo",
                "home_score": 2,
                "away_score": 1,
                "match_date": datetime(2020, 1, 1, tzinfo=UTC),
                "label": "1",
            }
        ]
    )
    monkeypatch.setattr(sync_mod, "load_fixtures", lambda **kwargs: df)

    out = tmp_path / "current.json"
    path = sync_current_round(season=2025, round_number=1, output_path=out)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["competition"] == "Brasileirão"
    assert data["matches"][0]["away_team"] == "Botafogo"
