"""Testes da camada silver in-play match_states."""
from __future__ import annotations

import pandas as pd

from pipelines.inplay_match_states import (
    _outcome_label,
    build_match_states_from_ticks,
    upsert_match_states,
)


def test_outcome_label():
    assert _outcome_label(2, 1) == "1"
    assert _outcome_label(0, 0) == "X"


def test_build_match_states_brier(tmp_path, monkeypatch):
    ticks = pd.DataFrame(
        [
            {
                "event_id": 100,
                "home_team": "Brasil",
                "away_team": "Marrocos",
                "minute": 45,
                "home_score": 1,
                "away_score": 0,
                "prob_final_home": 0.6,
                "prob_final_draw": 0.25,
                "prob_final_away": 0.15,
            }
        ]
    )
    finals = {100: {"home_score_final": 2, "away_score_final": 0, "y_final": "1"}}
    out = build_match_states_from_ticks(ticks, finals=finals)
    assert out.iloc[0]["y_final"] == "1"
    assert out.iloc[0]["brier_model"] is not None
    assert float(out.iloc[0]["brier_model"]) < 0.2


def test_upsert_match_states(tmp_path, monkeypatch):
    bronze = tmp_path / "bronze" / "superbet"
    bronze.mkdir(parents=True)
    silver = tmp_path / "silver" / "inplay"
    silver.mkdir(parents=True)

    ticks = pd.DataFrame(
        [
            {
                "event_id": 200,
                "home_team": "A",
                "away_team": "B",
                "minute": 60,
                "home_score": 0,
                "away_score": 0,
                "prob_final_home": 0.4,
                "prob_final_draw": 0.3,
                "prob_final_away": 0.3,
            }
        ]
    )
    ticks.to_parquet(bronze / "live_ticks.parquet", index=False)

    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    monkeypatch.setattr("pipelines.inplay_match_states.settings.lake_root", tmp_path)
    monkeypatch.setattr(
        "pipelines.inplay_match_states.MATCH_STATES_PATH",
        tmp_path / "silver" / "inplay" / "match_states.parquet",
    )
    monkeypatch.setattr(
        "ingest.superbet.live_ticks.live_ticks_path",
        lambda: tmp_path / "bronze" / "superbet" / "live_ticks.parquet",
    )

    path = upsert_match_states()
    assert path.exists()
    df = pd.read_parquet(path)
    assert len(df) == 1
