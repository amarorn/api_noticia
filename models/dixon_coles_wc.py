import math
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from models.poisson_wc import (
    MAX_GOALS,
    PoissonPrediction,
    expected_lambdas,
    score_outcome_probs,
    score_probability,
)
from pipelines.wc_training_dataset import wc_training_label_df
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import (
    WcMatchFeatures,
    build_match_features,
    precompute_elo_timeline,
    row_group_name,
)


def _normalized_score_prob(
    home_goals: int,
    away_goals: int,
    lam_home: float,
    lam_away: float,
    rho: float,
) -> float:
    total_mass = sum(
        score_probability(i, j, lam_home, lam_away, rho)
        for i in range(MAX_GOALS + 1)
        for j in range(MAX_GOALS + 1)
    )
    if total_mass <= 0:
        return 1e-12
    return score_probability(home_goals, away_goals, lam_home, lam_away, rho) / total_mass


class DixonColesWcModel:
    def __init__(self) -> None:
        self.rho: float = 0.0
        self._fitted = False

    def fit(
        self,
        fixtures_df: pd.DataFrame,
        holdout_season: int | None = 2022,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> dict:
        df = fixtures_df.sort_values("match_date").copy()
        train_df = (
            wc_training_label_df(df, holdout_season)
            if holdout_season
            else wc_training_label_df(df, None)
        )
        if train_df.empty:
            train_df = df

        self.rho = self._estimate_rho(fixtures_df, train_df, on_progress=on_progress)
        self._fitted = True
        return {"rho": round(self.rho, 4), "train_size": len(train_df)}

    def _estimate_rho(
        self,
        fixtures_df: pd.DataFrame,
        train_df: pd.DataFrame,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> float:
        if len(train_df) < 20:
            return 0.0

        elo_timeline = precompute_elo_timeline(fixtures_df)
        prepared: list[tuple[int, int, float, float]] = []
        train_total = len(train_df)
        for train_index, (_, row) in enumerate(train_df.iterrows(), start=1):
            before = row["match_date"]
            history = fixtures_df[fixtures_df["match_date"] < before]
            if history.empty:
                history = fixtures_df

            gcol = row_group_name(row)
            features = build_match_features(
                fixtures_df,
                row["home_team"],
                row["away_team"],
                before_date=before,
                phase=row.get("phase", "group"),
                is_neutral=bool(row.get("is_neutral", True)),
                season=int(row["season"]),
                group_name=gcol,
                elo_timeline=elo_timeline,
            )
            lam_home, lam_away = expected_lambdas(
                history,
                row["home_team"],
                row["away_team"],
                features=features,
                before_date=before,
            )
            prepared.append((int(row["home_score"]), int(row["away_score"]), lam_home, lam_away))
            if on_progress and (
                train_index == 1 or train_index % 25 == 0 or train_index == train_total
            ):
                on_progress(train_index, train_total)

        hp = get_wc_hyperparams()
        best_rho = 0.0
        best_ll = float("-inf")

        steps = int(round((hp.rho_max - hp.rho_min) / hp.rho_step))
        for i in range(steps + 1):
            if on_progress and (i == 0 or i % max(1, steps // 10) == 0 or i == steps):
                on_progress(i + 1, steps + 1)
            rho = hp.rho_min + i * hp.rho_step
            log_likelihood = 0.0
            for hs, aws, lam_home, lam_away in prepared:
                p = _normalized_score_prob(hs, aws, lam_home, lam_away, rho)
                log_likelihood += math.log(max(p, 1e-12))

            if log_likelihood > best_ll:
                best_ll = log_likelihood
                best_rho = rho

        return best_rho

    def predict(
        self,
        fixtures_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        features: WcMatchFeatures | None = None,
        before_date: datetime | None = None,
    ) -> PoissonPrediction:
        if not self._fitted:
            self.fit(fixtures_df)

        lam_home, lam_away = expected_lambdas(
            fixtures_df,
            home_team,
            away_team,
            features=features,
            before_date=before_date,
        )
        return score_outcome_probs(lam_home, lam_away, rho=self.rho)
