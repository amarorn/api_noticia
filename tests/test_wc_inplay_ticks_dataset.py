"""Testes do dataset MLE a partir de live_ticks."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from pipelines.wc_inplay_ticks_dataset import build_timeline_from_live_ticks


def test_build_timeline_from_live_ticks(tmp_path, monkeypatch):
    lake = tmp_path / "lake"
    bronze = lake / "bronze" / "superbet"
    events = bronze / "events" / "999"
    events.mkdir(parents=True)

    snapshot = {
        "home_team": "Tcheca",
        "away_team": "África do Sul",
        "inplay": {"home_score": 2, "away_score": 1},
    }
    (events / "latest.json").write_text(json.dumps(snapshot), encoding="utf-8")

    ticks = pd.DataFrame(
        [
            {
                "event_id": 999,
                "home_team": "Tcheca",
                "away_team": "África do Sul",
                "minute": 55,
                "home_score": 1,
                "away_score": 0,
                "home_corners": 4,
                "away_corners": 2,
                "home_red_cards": 0,
                "away_red_cards": 0,
            }
        ]
    )
    ticks.to_parquet(bronze / "live_ticks.parquet", index=False)

    monkeypatch.setattr("config.settings.lake_root", lake)
    monkeypatch.setattr(
        "pipelines.wc_inplay_ticks_dataset.live_ticks_path",
        lambda: bronze / "live_ticks.parquet",
    )
    monkeypatch.setattr(
        "pipelines.inplay_event_finals.load_all_event_final_scores",
        lambda **_kwargs: {
            999: {
                "event_id": 999,
                "home_score_final": 2,
                "away_score_final": 1,
            }
        },
    )

    df = build_timeline_from_live_ticks()
    assert len(df) == 1
    row = df.iloc[0]
    assert row["remaining_goals_home"] == 1
    assert row["remaining_goals_away"] == 1
    assert row["home_score_partial"] == 1
    assert row["source"] == "live_ticks"


def test_build_timeline_empty_without_ticks(tmp_path, monkeypatch):
    lake = tmp_path / "lake"
    monkeypatch.setattr("config.settings.lake_root", lake)
    monkeypatch.setattr(
        "pipelines.wc_inplay_ticks_dataset.live_ticks_path",
        lambda: lake / "bronze" / "superbet" / "live_ticks.parquet",
    )
    assert build_timeline_from_live_ticks().empty
