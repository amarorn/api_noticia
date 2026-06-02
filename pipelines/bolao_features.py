from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from pipelines.stats import compute_h2h
from schemas.models import BolaoFeature

FEATURE_NAMES = [
    "home_position",
    "away_position",
    "position_diff",
    "points_diff",
    "home_form_wins",
    "away_form_wins",
    "h2h_home_wins",
    "h2h_draws",
    "h2h_away_wins",
    "home_goal_diff",
    "away_goal_diff",
]


def _form_wins(form: str | None) -> float:
    if not form or form == "N/A":
        return 0.0
    return float(form.count("V"))


def build_bolao_feature(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    match_date: datetime,
    round_number: int,
    competition: str,
    match_id: str,
    season: int | None = None,
) -> BolaoFeature:
    features = BolaoFeature(
        match_id=match_id,
        home_team=home_team,
        away_team=away_team,
        round_number=round_number,
        competition=competition,
        match_date=match_date,
    )
    stats = compute_h2h(fixtures_df, home_team, away_team, match_date, season=season)
    if stats is None:
        return features
    return features.model_copy(
        update={
            "home_position": stats.home.position,
            "away_position": stats.away.position,
            "home_points": stats.home.points,
            "away_points": stats.away.points,
            "home_form": stats.home.form,
            "away_form": stats.away.form,
            "home_goals_for": stats.home.goals_for,
            "home_goals_against": stats.home.goals_against,
            "away_goals_for": stats.away.goals_for,
            "away_goals_against": stats.away.goals_against,
            "h2h_home_wins": stats.h2h_home_wins,
            "h2h_draws": stats.h2h_draws,
            "h2h_away_wins": stats.h2h_away_wins,
        }
    )


def feature_vector(features: BolaoFeature) -> list[float]:
    pos_home = float(features.home_position or 10)
    pos_away = float(features.away_position or 10)
    pts_home = float(features.home_points or 0)
    pts_away = float(features.away_points or 0)
    return [
        pos_home,
        pos_away,
        pos_away - pos_home,
        pts_home - pts_away,
        _form_wins(features.home_form),
        _form_wins(features.away_form),
        float(features.h2h_home_wins or 0),
        float(features.h2h_draws or 0),
        float(features.h2h_away_wins or 0),
        float((features.home_goals_for or 0) - (features.home_goals_against or 0)),
        float((features.away_goals_for or 0) - (features.away_goals_against or 0)),
    ]


def features_to_array(rows: list[BolaoFeature]) -> np.ndarray:
    return np.array([feature_vector(r) for r in rows], dtype=float)
