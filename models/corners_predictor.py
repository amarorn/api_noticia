from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from ingest.fixtures.world_cup import load_wc_fixtures
from ingest.sofascore.corners_dataset import corners_training_summary, load_corners_history
from models.poisson_corners import (
    CornerModelFactors,
    CornersPrediction,
    corner_model_factors,
    predict_corners,
)
from models.poisson_wc import goal_model_factors
from pipelines.wc_stats import WcMatchFeatures, build_match_features


@dataclass
class CornersMatchPrediction:
    home_team: str
    away_team: str
    prediction: CornersPrediction
    factors: CornerModelFactors
    training_summary: dict
    data_source: str


class CornersPredictor:
    def __init__(
        self,
        *,
        corners_df: pd.DataFrame | None = None,
        fixtures_df: pd.DataFrame | None = None,
    ) -> None:
        self.corners_df = corners_df if corners_df is not None else load_corners_history()
        self.fixtures = fixtures_df if fixtures_df is not None else load_wc_fixtures()

    def predict(
        self,
        home_team: str,
        away_team: str,
        *,
        phase: str = "group",
        is_neutral: bool = True,
        before_date: datetime | None = None,
        season: int | None = None,
        group_name: str | None = None,
    ) -> CornersMatchPrediction:
        cutoff = before_date or datetime.now(timezone.utc)
        features = build_match_features(
            self.fixtures,
            home_team,
            away_team,
            before_date=cutoff,
            phase=phase,
            is_neutral=is_neutral,
            season=season,
            group_name=group_name,
        )

        goal_factors = goal_model_factors(
            self.fixtures,
            home_team,
            away_team,
            features=features,
            before_date=cutoff,
        )
        goal_lam_home = goal_factors.lambda_home
        goal_lam_away = goal_factors.lambda_away
        league_goal_avg = goal_factors.league_avg

        factors = corner_model_factors(
            self.corners_df,
            home_team,
            away_team,
            features=features,
            before_date=cutoff,
            goal_lam_home=goal_lam_home,
            goal_lam_away=goal_lam_away,
            league_goal_avg=league_goal_avg,
        )
        prediction = predict_corners(factors.lambda_home, factors.lambda_away)

        data_source = "sofascore_corners"
        if factors.training_matches == 0:
            data_source = "goal_proxy_default"
        elif factors.blend_with_goal_proxy > 0:
            data_source = "sofascore_corners+goal_proxy"

        return CornersMatchPrediction(
            home_team=home_team,
            away_team=away_team,
            prediction=prediction,
            factors=factors,
            training_summary=corners_training_summary(
                load_corners_history(before_date=cutoff)
            ),
            data_source=data_source,
        )
