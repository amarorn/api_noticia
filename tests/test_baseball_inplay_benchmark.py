"""Testes do benchmark Brier de beisebol in-play."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from pipelines.baseball_inplay_benchmark import (
    compute_baseball_live_ticks_brier,
    list_baseball_event_ids,
)


def test_list_baseball_event_ids(tmp_path: Path, monkeypatch):
    bronze = tmp_path / "bronze"
    events = bronze / "superbet" / "events"
    (events / "100").mkdir(parents=True)
    (events / "200").mkdir(parents=True)
    (events / "100" / "latest.json").write_text(
        json.dumps({"sport_id": 20, "home_team": "A", "away_team": "B"}),
        encoding="utf-8",
    )
    (events / "200" / "latest.json").write_text(
        json.dumps({"sport_id": 1, "home_team": "X", "away_team": "Y"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "pipelines.baseball_inplay_benchmark.settings",
        SimpleNamespace(bronze_path=bronze, baseball_sport_id=20),
    )
    assert list_baseball_event_ids(sport_id=20) == {100}


def test_compute_baseball_brier_resolved(tmp_path: Path, monkeypatch):
    bronze = tmp_path / "bronze"
    events = bronze / "superbet" / "events" / "501"
    events.mkdir(parents=True)
    (events / "latest.json").write_text(
        json.dumps({"sport_id": 20, "home_team": "Yankees", "away_team": "Sox"}),
        encoding="utf-8",
    )
    ticks_path = bronze / "superbet" / "live_ticks.parquet"
    ticks_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "event_id": 501,
                "minute": 3,
                "home_score": 1,
                "away_score": 0,
                "status": "STARTED",
                "prob_final_home": 0.62,
                "prob_final_away": 0.38,
                "prob_final_draw": 0.0,
                "captured_at": pd.Timestamp("2026-07-18T12:00:00Z"),
            },
            {
                "event_id": 501,
                "minute": 9,
                "home_score": 5,
                "away_score": 2,
                "status": "FINISHED",
                "prob_final_home": 0.95,
                "prob_final_away": 0.05,
                "prob_final_draw": 0.0,
                "captured_at": pd.Timestamp("2026-07-18T14:00:00Z"),
            },
        ]
    ).to_parquet(ticks_path, index=False)

    monkeypatch.setattr(
        "pipelines.baseball_inplay_benchmark.settings",
        SimpleNamespace(bronze_path=bronze, baseball_sport_id=20),
    )
    monkeypatch.setattr(
        "pipelines.baseball_inplay_benchmark.live_ticks_path",
        lambda: ticks_path,
    )

    report = compute_baseball_live_ticks_brier(verbose=True, sport_id=20)
    assert "error" not in report
    assert report["n_events_resolved"] == 1
    assert report["n_ticks_scored"] == 2
    assert 0.0 <= report["brier_mean"] <= 1.0
    assert report["accuracy_mean"] == 1.0
