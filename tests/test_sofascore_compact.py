from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ingest.sofascore.compact_stats import compact_match_stats_json
from ingest.sofascore.paths import MATCH_STATS_PARQUET


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_compact_match_stats_json_dedup_by_event_id(tmp_path: Path):
    stats_dir = tmp_path / "sofascore"
    stats_dir.mkdir()
    _write_json(
        stats_dir / "1_Brasil_x_Argentina_stats.json",
        {
            "event_id": 1,
            "home_team": "Brasil",
            "away_team": "Argentina",
            "match_date": "2022-11-20",
            "home_xg": 1.1,
            "fetched_at": "2026-01-01T00:00:00+00:00",
        },
    )
    _write_json(
        stats_dir / "1_Brasil_x_Argentina_v2_stats.json",
        {
            "event_id": 1,
            "home_team": "Brasil",
            "away_team": "Argentina",
            "match_date": "2022-11-20",
            "home_xg": 2.2,
            "fetched_at": "2026-06-01T00:00:00+00:00",
        },
    )
    _write_json(
        stats_dir / "2_Portugal_x_Suíça_stats.json",
        {
            "event_id": 2,
            "home_team": "Portugal",
            "away_team": "Suíça",
            "match_date": "2022-12-06",
            "home_xg": 2.36,
            "fetched_at": "2026-06-01T00:00:00+00:00",
        },
    )

    report = compact_match_stats_json(stats_dir=stats_dir, merge_existing=False)

    assert report.json_files == 3
    assert report.rows_written == 2
    parquet = stats_dir / MATCH_STATS_PARQUET
    df = pd.read_parquet(parquet)
    assert len(df) == 2
    brasil = df[df["event_id"] == 1].iloc[0]
    assert float(brasil["home_xg"]) == 2.2


def test_compact_merges_existing_parquet(tmp_path: Path):
    stats_dir = tmp_path / "sofascore"
    stats_dir.mkdir()
    existing = pd.DataFrame(
        [
            {
                "event_id": 99,
                "home_team": "França",
                "away_team": "Alemanha",
                "match_date": "2018-07-15",
                "home_xg": 1.0,
            }
        ]
    )
    existing.to_parquet(stats_dir / MATCH_STATS_PARQUET, index=False)
    _write_json(
        stats_dir / "1_Brasil_x_Argentina_stats.json",
        {
            "event_id": 1,
            "home_team": "Brasil",
            "away_team": "Argentina",
            "match_date": "2022-11-20",
            "home_xg": 1.5,
        },
    )

    report = compact_match_stats_json(stats_dir=stats_dir, merge_existing=True)

    assert report.rows_written == 2
    df = pd.read_parquet(stats_dir / MATCH_STATS_PARQUET)
    assert set(df["event_id"].tolist()) == {1, 99}
