from __future__ import annotations

import pandas as pd
import pytest

from ingest.sofascore.paths import MATCH_STATS_PARQUET
from pipelines.lake_query import lake_summary, query_lake, team_sofascore_summary


duckdb = pytest.importorskip("duckdb")


def test_lake_summary_includes_sofascore(tmp_path, monkeypatch):
    sofascore_dir = tmp_path / "sofascore"
    sofascore_dir.mkdir()
    pd.DataFrame(
        [
            {
                "event_id": 1,
                "home_team": "Brasil",
                "away_team": "Argentina",
                "match_date": "2022-11-20",
                "home_xg": 1.8,
                "away_xg": 0.9,
                "home_corners": 5,
                "away_corners": 3,
            }
        ]
    ).to_parquet(sofascore_dir / MATCH_STATS_PARQUET, index=False)

    lake_root = tmp_path / "lake"
    monkeypatch.setattr("pipelines.lake_query.settings.lake_root", lake_root)
    monkeypatch.setattr("pipelines.lake_query.settings.sofascore_stats_dir", sofascore_dir)

    summary = lake_summary()
    assert summary["layers"]["sofascore"]["available"] is True
    assert summary["layers"]["sofascore"]["rows"] == 1


def test_team_sofascore_summary(tmp_path, monkeypatch):
    sofascore_dir = tmp_path / "sofascore"
    sofascore_dir.mkdir()
    pd.DataFrame(
        [
            {
                "event_id": 1,
                "home_team": "Brasil",
                "away_team": "Argentina",
                "match_date": "2022-11-20",
                "home_xg": 1.8,
                "away_xg": 0.9,
                "home_corners": 5,
                "away_corners": 3,
            },
            {
                "event_id": 2,
                "home_team": "Portugal",
                "away_team": "Brasil",
                "match_date": "2022-12-09",
                "home_xg": 1.1,
                "away_xg": 2.0,
                "home_corners": 4,
                "away_corners": 6,
            },
        ]
    ).to_parquet(sofascore_dir / MATCH_STATS_PARQUET, index=False)

    lake_root = tmp_path / "lake"
    monkeypatch.setattr("pipelines.lake_query.settings.lake_root", lake_root)
    monkeypatch.setattr("pipelines.lake_query.settings.sofascore_stats_dir", sofascore_dir)

    df = team_sofascore_summary("Brasil", limit=5)
    assert len(df) == 2

    avg = query_lake(
        "SELECT ROUND(AVG(home_xg), 2) AS avg_home_xg "
        "FROM sofascore WHERE home_team = 'Brasil'"
    )
    assert float(avg.iloc[0]["avg_home_xg"]) == 1.8
