from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd
import pytest

from models.corners_predictor import CornersPredictor
from models.poisson_corners import (
    blend_with_goal_proxy,
    corner_model_factors,
    predict_corners,
)
from pipelines.wc_stats import build_match_features


def _sample_corners_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event_id": 1,
                "home_team": "Brasil",
                "away_team": "Argentina",
                "match_date": datetime(2024, 6, 10, tzinfo=timezone.utc),
                "season": 2024,
                "home_corners": 8,
                "away_corners": 4,
            },
            {
                "event_id": 2,
                "home_team": "Brasil",
                "away_team": "França",
                "match_date": datetime(2024, 7, 1, tzinfo=timezone.utc),
                "season": 2024,
                "home_corners": 6,
                "away_corners": 5,
            },
            {
                "event_id": 3,
                "home_team": "Argentina",
                "away_team": "Brasil",
                "match_date": datetime(2023, 11, 15, tzinfo=timezone.utc),
                "season": 2023,
                "home_corners": 3,
                "away_corners": 7,
            },
            {
                "event_id": 4,
                "home_team": "Marrocos",
                "away_team": "Espanha",
                "match_date": datetime(2022, 12, 6, tzinfo=timezone.utc),
                "season": 2022,
                "home_corners": 2,
                "away_corners": 9,
            },
        ]
    )


def test_predict_corners_line_probs_sum():
    pred = predict_corners(5.2, 4.1)
    assert pred.expected_total_corners == pytest.approx(9.3, rel=1e-6)
    assert math.isclose(
        pred.line_probs["over_9.5"] + pred.line_probs["under_9.5"],
        1.0,
        rel_tol=1e-6,
    )
    assert math.isclose(
        pred.prob_home_more + pred.prob_draw_corners + pred.prob_away_more,
        1.0,
        rel_tol=1e-6,
    )


def test_blend_with_goal_proxy_increases_weight_when_sparse():
    home, away, weight = blend_with_goal_proxy(
        5.0,
        4.0,
        2.0,
        1.5,
        league_corner_avg=5.0,
        league_goal_avg=1.3,
        sample_matches=2,
        min_samples=8,
    )
    assert weight > 0.5
    assert home != 5.0


def test_corner_model_factors_from_history():
    df = _sample_corners_df()
    factors = corner_model_factors(
        df,
        "Brasil",
        "Argentina",
        before_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        goal_lam_home=1.8,
        goal_lam_away=1.1,
        league_goal_avg=1.3,
    )
    assert factors.lambda_home > 0
    assert factors.lambda_away > 0
    assert factors.training_matches >= 3


def test_corner_model_handles_nan_season():
    df = _sample_corners_df()
    df.loc[0, "season"] = float("nan")
    df.loc[0, "match_date"] = pd.NaT
    factors = corner_model_factors(
        df,
        "Brasil",
        "Argentina",
        before_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        goal_lam_home=1.8,
        goal_lam_away=1.1,
        league_goal_avg=1.3,
    )
    assert factors.lambda_home > 0
    assert factors.lambda_away > 0


def test_corners_predictor_with_fixtures():
    from ingest.fixtures.world_cup import load_wc_fixtures

    fixtures = load_wc_fixtures()
    if fixtures.empty:
        pytest.skip("fixtures WC ausentes")

    predictor = CornersPredictor(
        corners_df=_sample_corners_df(),
        fixtures_df=fixtures,
    )
    row = fixtures.iloc[0]
    before = pd.to_datetime(row["match_date"], utc=True).to_pydatetime()
    result = predictor.predict(
        row["home_team"],
        row["away_team"],
        before_date=before,
        is_neutral=bool(row.get("is_neutral", True)),
        season=int(row["season"]),
    )
    assert result.prediction.expected_total_corners > 0
    assert "over_9.5" in result.prediction.line_probs
