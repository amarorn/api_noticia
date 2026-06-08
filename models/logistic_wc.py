from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import structlog
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from models.wc_feature_cache import load_cached_features, save_cached_features
from pipelines.wc_holdout import wc_holdout_test_df, wc_holdout_train_df
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_sofascore_features import SOFASCORE_FEATURE_NAMES
from pipelines.wc_stats import (
    FEATURE_NAMES,
    build_match_features,
    features_to_vector,
    precompute_elo_timeline,
    row_group_name,
)
from schemas.models import BolaoLabel

LABELS: list[BolaoLabel] = ["1", "X", "2"]
_log = structlog.get_logger()


@dataclass
class LogisticPrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    prediction: BolaoLabel


class WcLogisticModel:
    def __init__(self) -> None:
        hp = get_wc_hyperparams()
        base = LogisticRegression(
            C=hp.logistic_c,
            class_weight=hp.logistic_class_weight,
            max_iter=hp.logistic_max_iter,
            random_state=42,
            solver="lbfgs",
        )
        self.model = CalibratedClassifierCV(
            base,
            cv=max(2, hp.logistic_calibration_cv),
            method="sigmoid",
        )
        self.scaler = StandardScaler()
        self._fitted = False

    def fit(
        self,
        fixtures_df: pd.DataFrame,
        holdout_season: int | None = 2022,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        df = fixtures_df.sort_values("match_date").copy()
        train_df = (
            wc_holdout_train_df(df, holdout_season)
            if holdout_season
            else df
        )

        cached = load_cached_features(train_df)
        if cached:
            x_rows, y_rows = cached
            _log.info("wc_logistic_features_cache_hit", train_size=len(y_rows))
            if on_progress:
                on_progress(len(y_rows), len(y_rows), "features (cache)")
        else:
            elo_timeline = precompute_elo_timeline(df)
            x_rows = []
            y_rows = []
            train_total = len(train_df)
            _log.info("wc_logistic_features_build_start", train_size=train_total)

            for index, (_, row) in enumerate(train_df.iterrows(), start=1):
                before = row["match_date"]
                gcol = row_group_name(row)
                feats = build_match_features(
                    df,
                    row["home_team"],
                    row["away_team"],
                    before_date=before,
                    phase=row.get("phase", "group"),
                    is_neutral=bool(row.get("is_neutral", True)),
                    season=int(row["season"]),
                    group_name=gcol if gcol is not None and not pd.isna(gcol) else None,
                    elo_timeline=elo_timeline,
                )
                x_rows.append(features_to_vector(feats, before_date=before))
                y_rows.append(row["label"])
                if on_progress and (index == 1 or index % 25 == 0 or index == train_total):
                    on_progress(index, train_total, "features")

            save_cached_features(train_df, x_rows, y_rows)
            _log.info("wc_logistic_features_build_done", train_size=len(y_rows))

        if len(x_rows) < 50:
            raise ValueError(f"Dados insuficientes para treino ({len(x_rows)} jogos)")

        hp = get_wc_hyperparams()
        if on_progress:
            on_progress(0, 1, "calibracao")
        _log.info(
            "wc_logistic_calibration_start",
            samples=len(x_rows),
            cv=hp.logistic_calibration_cv,
            max_iter=hp.logistic_max_iter,
        )

        x_scaled = self.scaler.fit_transform(x_rows)
        self.model.fit(x_scaled, y_rows)
        self._fitted = True
        _log.info("wc_logistic_calibration_done", samples=len(x_rows))

        metrics: dict = {
            "train_size": len(x_rows),
            "features": FEATURE_NAMES,
            "calibration": f"platt_sigmoid_cv{hp.logistic_calibration_cv}",
        }
        if holdout_season and holdout_season in df["season"].values:
            test_df = wc_holdout_test_df(df, holdout_season)
            correct = 0
            holdout_total = len(test_df)
            for holdout_index, (_, row) in enumerate(test_df.iterrows(), start=1):
                pred = self.predict_match(
                    df[df["match_date"] < row["match_date"]],
                    row["home_team"],
                    row["away_team"],
                    phase=row.get("phase", "group"),
                    is_neutral=bool(row.get("is_neutral", True)),
                    before_date=row["match_date"],
                    season=int(row["season"]),
                    group_name=row_group_name(row),
                )
                if pred.prediction == row["label"]:
                    correct += 1
                if on_progress and (
                    holdout_index == 1
                    or holdout_index % 5 == 0
                    or holdout_index == holdout_total
                ):
                    on_progress(holdout_index, holdout_total, "holdout")
            metrics["holdout_season"] = holdout_season
            metrics["holdout_accuracy"] = correct / len(test_df) if len(test_df) else 0.0

        return metrics

    def predict_match(
        self,
        fixtures_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        phase: str = "group",
        is_neutral: bool = True,
        before_date: datetime | None = None,
        season: int | None = None,
        group_name: str | None = None,
        include_sofascore: bool = True,
    ) -> LogisticPrediction:
        if not self._fitted:
            self.fit(fixtures_df)

        feats = build_match_features(
            fixtures_df,
            home_team,
            away_team,
            before_date=before_date,
            phase=phase,
            is_neutral=is_neutral,
            season=season,
            group_name=group_name,
        )
        x = features_to_vector(feats, before_date=before_date)
        if not include_sofascore:
            start = len(FEATURE_NAMES) - len(SOFASCORE_FEATURE_NAMES)
            for i in range(start, len(x)):
                x[i] = 0.0
        x = self.scaler.transform([x])[0]
        probs = self.model.predict_proba([x])[0]
        classes = list(self.model.classes_)

        prob_map = {c: float(p) for c, p in zip(classes, probs, strict=False)}
        p1 = prob_map.get("1", 0.0)
        px = prob_map.get("X", 0.0)
        p2 = prob_map.get("2", 0.0)

        best = max(prob_map, key=prob_map.get)
        return LogisticPrediction(
            prob_home=p1,
            prob_draw=px,
            prob_away=p2,
            prediction=best,  # type: ignore[arg-type]
        )
