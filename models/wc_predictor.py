from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from ingest.fixtures.world_cup import load_wc_fixtures
from models.wc_collaborative import CollaborativeWcModel
from models.logistic_wc import WcLogisticModel
from models.poisson_wc import predict_poisson
from pipelines.wc_stats import build_match_features, compute_wc_h2h, format_wc_context
from schemas.models import BolaoLabel


@dataclass
class WcPrediction:
    home_team: str
    away_team: str
    prediction: BolaoLabel
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    poisson_score: str
    expected_goals: str
    context: str
    h2h_summary: str
    model_breakdown: dict


class WcPredictor:
    def __init__(self, fixtures_df: pd.DataFrame | None = None) -> None:
        self.fixtures = fixtures_df if fixtures_df is not None else load_wc_fixtures()
        if self.fixtures.empty:
            raise ValueError(
                "Nenhum dado de Copa do Mundo. Execute: import-world-cup"
            )
        self.logistic = WcLogisticModel()
        self._metrics = self.logistic.fit(self.fixtures, holdout_season=2022)
        self.collaborative = CollaborativeWcModel()
        self.collab_metrics = self.collaborative.fit(self.fixtures, validation_season=2022)

    @property
    def training_metrics(self) -> dict:
        return self._metrics

    def predict(
        self,
        home_team: str,
        away_team: str,
        phase: str = "group",
        is_neutral: bool = True,
    ) -> WcPrediction:
        now = datetime.now(timezone.utc)
        features = build_match_features(
            self.fixtures,
            home_team,
            away_team,
            before_date=now,
            phase=phase,
            is_neutral=is_neutral,
        )
        h2h = compute_wc_h2h(self.fixtures, home_team, away_team, before_date=now)

        poisson = predict_poisson(
            self.fixtures,
            home_team,
            away_team,
            features,
            before_date=now,
        )
        logistic = self.logistic.predict_match(
            self.fixtures, home_team, away_team, phase=phase, is_neutral=is_neutral
        )

        pw = self.collaborative.poisson_weight
        lw = self.collaborative.logistic_weight
        prob_home = pw * poisson.prob_home + lw * logistic.prob_home
        prob_draw = pw * poisson.prob_draw + lw * logistic.prob_draw
        prob_away = pw * poisson.prob_away + lw * logistic.prob_away

        total = prob_home + prob_draw + prob_away
        prob_home /= total
        prob_draw /= total
        prob_away /= total

        probs = {"1": prob_home, "X": prob_draw, "2": prob_away}
        prediction = max(probs, key=probs.get)  # type: ignore[assignment]
        confidence = probs[prediction]

        h2h_summary = (
            f"{h2h.total} jogos em Copas | "
            f"{home_team} {h2h.home_wins}V {h2h.draws}E {h2h.away_wins}D {away_team}"
        )
        if h2h.last_results:
            h2h_summary += f" | Sequência: {' '.join(h2h.last_results)}"

        return WcPrediction(
            home_team=home_team,
            away_team=away_team,
            prediction=prediction,
            confidence=confidence,
            prob_home=prob_home,
            prob_draw=prob_draw,
            prob_away=prob_away,
            poisson_score=poisson.most_likely_score,
            expected_goals=f"{poisson.expected_home_goals:.1f}x{poisson.expected_away_goals:.1f}",
            context=format_wc_context(features, h2h),
            h2h_summary=h2h_summary,
            model_breakdown={
                "poisson": {
                    "1": round(poisson.prob_home, 3),
                    "X": round(poisson.prob_draw, 3),
                    "2": round(poisson.prob_away, 3),
                },
                "logistic": {
                    "1": round(logistic.prob_home, 3),
                    "X": round(logistic.prob_draw, 3),
                    "2": round(logistic.prob_away, 3),
                },
                "holdout_2022_accuracy": self._metrics.get("holdout_accuracy"),
                "ensemble_weights": {
                    "poisson": round(pw, 3),
                    "logistic": round(lw, 3),
                },
                "ensemble_brier": round(self.collab_metrics.brier_score, 6),
            },
        )
