import json
from datetime import datetime, timezone

import pandas as pd

from ingest.gcp.medallion import LAYER_ALIASES, MEDALLION_TABLES, resolve_layer
from ingest.sofascore.bronze_dataset import load_bronze_sofascore_events
from pipelines.wc_sofascore_features import (
    SOFASCORE_FEATURE_NAMES,
    build_gold_wc_match_features_df,
)


def test_medallion_table_names():
    assert MEDALLION_TABLES["silver_sofascore"] == "silver_sofascore_match_stats"
    assert MEDALLION_TABLES["silver_fixtures"] == "silver_fixtures_results"
    assert MEDALLION_TABLES["bronze_sofascore"] == "bronze_sofascore_events"
    assert MEDALLION_TABLES["gold_wc"] == "gold_wc_match_features"


def test_layer_aliases_resolve():
    assert resolve_layer("sofascore") == "silver_sofascore"
    assert resolve_layer("fixtures") == "silver_fixtures"
    assert LAYER_ALIASES["sofascore"] == "silver_sofascore"


def test_load_bronze_sofascore_events(tmp_path):
    payload = {
        "event_id": 99,
        "home_team": "Brasil",
        "away_team": "Argentina",
        "match_date": "2024-06-15T20:00:00+00:00",
        "source": "sofascore",
        "fetched_at": "2024-06-16T00:00:00+00:00",
        "home_xg": 1.5,
    }
    path = tmp_path / "99_Brasil_x_Argentina_stats.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    df = load_bronze_sofascore_events(stats_dir=tmp_path)
    assert len(df) == 1
    assert df.iloc[0]["event_id"] == 99
    assert "home_xg" in df.iloc[0]["payload_json"]


def test_build_gold_wc_match_features_df():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    history = pd.DataFrame(
        [
            {
                "event_id": 1,
                "home_team": "Brasil",
                "away_team": "Alemanha",
                "match_date": base,
                "home_xg": 2.0,
                "away_xg": 1.0,
                "home_possession_pct": 60.0,
                "away_possession_pct": 40.0,
                "home_shots_on_target": 6.0,
                "away_shots_on_target": 3.0,
                "home_big_chances": 4.0,
                "away_big_chances": 2.0,
            },
            {
                "event_id": 2,
                "home_team": "Brasil",
                "away_team": "Argentina",
                "match_date": base + pd.Timedelta(days=30),
                "home_xg": 1.8,
                "away_xg": 1.2,
                "home_possession_pct": 58.0,
                "away_possession_pct": 42.0,
                "home_shots_on_target": 5.0,
                "away_shots_on_target": 4.0,
                "home_big_chances": 3.0,
                "away_big_chances": 2.0,
            },
            {
                "event_id": 3,
                "home_team": "Argentina",
                "away_team": "França",
                "match_date": base + pd.Timedelta(days=15),
                "home_xg": 1.5,
                "away_xg": 1.4,
                "home_possession_pct": 55.0,
                "away_possession_pct": 45.0,
                "home_shots_on_target": 5.0,
                "away_shots_on_target": 4.0,
                "home_big_chances": 3.0,
                "away_big_chances": 2.0,
            },
            {
                "event_id": 4,
                "home_team": "Argentina",
                "away_team": "França",
                "match_date": base + pd.Timedelta(days=45),
                "home_xg": 1.6,
                "away_xg": 1.3,
                "home_possession_pct": 56.0,
                "away_possession_pct": 44.0,
                "home_shots_on_target": 5.0,
                "away_shots_on_target": 4.0,
                "home_big_chances": 3.0,
                "away_big_chances": 2.0,
            },
        ]
    )
    gold = build_gold_wc_match_features_df(stats_df=history)
    assert len(gold) == 4
    assert list(gold.columns)[-7:-1] == SOFASCORE_FEATURE_NAMES
    second = gold[gold["event_id"] == 2].iloc[0]
    assert second["sofa_stats_available"] == 1.0
