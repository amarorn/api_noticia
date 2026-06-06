from datetime import datetime, timezone

import pandas as pd

from pipelines.wc_sofascore_features import (
    SOFASCORE_FEATURE_NAMES,
    format_sofascore_context,
    sofascore_breakdown,
    sofascore_feature_vector,
    team_rolling_stats,
)


def _stats_df() -> pd.DataFrame:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(5):
        rows.append(
            {
                "event_id": 1000 + i,
                "home_team": "Brasil",
                "away_team": "Alemanha",
                "match_date": base + pd.Timedelta(days=i * 7),
                "home_xg": 2.0 + i * 0.1,
                "away_xg": 1.0,
                "home_possession_pct": 60.0,
                "away_possession_pct": 40.0,
                "home_shots_on_target": 6.0,
                "away_shots_on_target": 3.0,
                "home_big_chances": 4.0,
                "away_big_chances": 2.0,
                "home_corners": 5.0,
                "away_corners": 4.0,
            }
        )
        rows.append(
            {
                "event_id": 2000 + i,
                "home_team": "Argentina",
                "away_team": "França",
                "match_date": base + pd.Timedelta(days=i * 7),
                "home_xg": 1.5,
                "away_xg": 1.2,
                "home_possession_pct": 55.0,
                "away_possession_pct": 45.0,
                "home_shots_on_target": 5.0,
                "away_shots_on_target": 4.0,
                "home_big_chances": 3.0,
                "away_big_chances": 2.0,
                "home_corners": 6.0,
                "away_corners": 5.0,
            }
        )
    return pd.DataFrame(rows)


def test_sofascore_features_neutral_without_history():
    vec = sofascore_feature_vector("Brasil", "Argentina", stats_df=pd.DataFrame())
    assert vec == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert len(SOFASCORE_FEATURE_NAMES) == 6


def test_team_rolling_stats_requires_minimum_matches():
    df = _stats_df()
    brasil = team_rolling_stats(df, "Brasil")
    assert brasil is not None
    assert brasil.samples == 5
    assert brasil.xg_for > 2.0

    single = df.head(1)
    assert team_rolling_stats(single, "Brasil") is None


def test_sofascore_feature_vector_diff_and_availability():
    df = _stats_df()
    cutoff = datetime(2024, 3, 1, tzinfo=timezone.utc)
    vec = sofascore_feature_vector(
        "Brasil",
        "Argentina",
        before_date=cutoff,
        stats_df=df,
    )
    assert vec[-1] == 1.0
    assert vec[0] > 0.0
    assert vec[2] == 5.0


def test_sofascore_breakdown_and_context():
    df = _stats_df()
    cutoff = datetime(2024, 3, 1, tzinfo=timezone.utc)
    info = sofascore_breakdown("Brasil", "Argentina", before_date=cutoff, stats_df=df)
    assert info["available"] is True
    assert info["home_last5"]["samples"] == 5
    ctx = format_sofascore_context("Brasil", "Argentina", before_date=cutoff)
    assert ctx is not None
    assert "Sofascore" in ctx
    assert "Δ xG a favor" in ctx
