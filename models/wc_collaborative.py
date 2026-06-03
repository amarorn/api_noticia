from dataclasses import dataclass
from datetime import datetime, timezone
from math import log

import pandas as pd

from models.dixon_coles_wc import DixonColesWcModel
from models.logistic_wc import WcLogisticModel
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import build_match_features


@dataclass
class CollaborativeMetrics:
    dixon_coles_weight: float
    logistic_weight: float
    accuracy: float
    brier_score: float
    log_loss: float
    validation_size: int


def _brier_multiclass(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    labels = ("1", "X", "2")
    total = 0.0
    for row in rows:
        y = row["label"]
        probs = row["probs"]
        for label in labels:
            target = 1.0 if y == label else 0.0
            total += (probs[label] - target) ** 2
    return total / (len(rows) * len(labels))


def _log_loss_multiclass(rows: list[dict], epsilon: float = 1e-12) -> float:
    if not rows:
        return 0.0
    total = 0.0
    for row in rows:
        p = max(min(row["probs"][row["label"]], 1.0 - epsilon), epsilon)
        total += -log(p)
    return total / len(rows)


class CollaborativeWcModel:
    def __init__(self, dixon_coles: DixonColesWcModel | None = None) -> None:
        self.logistic = WcLogisticModel()
        self.dixon_coles = dixon_coles or DixonColesWcModel()
        self.metrics: CollaborativeMetrics | None = None
        self._dixon_coles_weight = 0.5

    @property
    def dixon_coles_weight(self) -> float:
        return self._dixon_coles_weight

    @property
    def poisson_weight(self) -> float:
        return self._dixon_coles_weight

    @property
    def logistic_weight(self) -> float:
        return 1.0 - self._dixon_coles_weight

    def fit(
        self,
        fixtures_df: pd.DataFrame,
        validation_season: int = 2022,
        logistic_model: WcLogisticModel | None = None,
    ) -> CollaborativeMetrics:
        df = fixtures_df.sort_values("match_date").copy()
        train_df = df[df["season"] != validation_season]
        valid_df = df[df["season"] == validation_season]

        if train_df.empty or valid_df.empty:
            raise ValueError(
                f"Não foi possível separar treino/validação para a temporada {validation_season}."
            )

        if logistic_model is not None:
            self.logistic = logistic_model
        else:
            self.logistic.fit(train_df, holdout_season=None)
        if not self.dixon_coles._fitted:
            self.dixon_coles.fit(df, holdout_season=validation_season)

        base_rows: list[dict] = []
        for _, row in valid_df.iterrows():
            before = row["match_date"]
            history_mask = pd.to_datetime(df["match_date"], utc=True) < pd.to_datetime(before, utc=True)
            history = df[history_mask]
            if history.empty:
                continue

            phase = row.get("phase", "group")
            is_neutral = bool(row.get("is_neutral", True))

            features = build_match_features(
                history,
                row["home_team"],
                row["away_team"],
                before_date=before,
                phase=phase,
                is_neutral=is_neutral,
            )
            dc = self.dixon_coles.predict(
                history,
                row["home_team"],
                row["away_team"],
                features=features,
                before_date=before,
            )
            logistic = self.logistic.predict_match(
                history,
                row["home_team"],
                row["away_team"],
                phase=phase,
                is_neutral=is_neutral,
            )
            base_rows.append(
                {
                    "label": row["label"],
                    "dixon_coles": {"1": dc.prob_home, "X": dc.prob_draw, "2": dc.prob_away},
                    "logistic": {"1": logistic.prob_home, "X": logistic.prob_draw, "2": logistic.prob_away},
                }
            )

        if not base_rows:
            raise ValueError("Não foi possível gerar previsões para calibração.")

        hp = get_wc_hyperparams()
        steps = max(hp.ensemble_weight_steps, 1)
        best: dict | None = None
        for step in range(0, steps + 1):
            dw = step / steps
            lw = 1.0 - dw

            scored_rows: list[dict] = []
            correct = 0
            for item in base_rows:
                probs = {
                    "1": dw * item["dixon_coles"]["1"] + lw * item["logistic"]["1"],
                    "X": dw * item["dixon_coles"]["X"] + lw * item["logistic"]["X"],
                    "2": dw * item["dixon_coles"]["2"] + lw * item["logistic"]["2"],
                }
                total = probs["1"] + probs["X"] + probs["2"]
                probs = {k: v / total for k, v in probs.items()}
                pred = max(probs, key=probs.get)
                if pred == item["label"]:
                    correct += 1
                scored_rows.append({"label": item["label"], "probs": probs})

            candidate = {
                "dw": dw,
                "lw": lw,
                "accuracy": correct / len(scored_rows),
                "brier": _brier_multiclass(scored_rows),
                "log_loss": _log_loss_multiclass(scored_rows),
                "size": len(scored_rows),
            }
            if best is None or candidate["brier"] < best["brier"]:
                best = candidate

        assert best is not None
        self._dixon_coles_weight = float(best["dw"])
        self.metrics = CollaborativeMetrics(
            dixon_coles_weight=float(best["dw"]),
            logistic_weight=float(best["lw"]),
            accuracy=float(best["accuracy"]),
            brier_score=float(best["brier"]),
            log_loss=float(best["log_loss"]),
            validation_size=int(best["size"]),
        )
        return self.metrics

    def predict(
        self,
        fixtures_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        *,
        phase: str = "group",
        is_neutral: bool = True,
        before_date: datetime | None = None,
    ) -> dict[str, float]:
        if self.metrics is None:
            self.fit(fixtures_df)

        ref = before_date or datetime.now(timezone.utc)
        dt = pd.to_datetime(fixtures_df["match_date"], utc=True)
        ref_ts = pd.Timestamp(ref if ref.tzinfo else ref.replace(tzinfo=timezone.utc))
        history = fixtures_df[dt < ref_ts]
        if history.empty:
            history = fixtures_df

        features = build_match_features(
            history,
            home_team,
            away_team,
            before_date=ref,
            phase=phase,
            is_neutral=is_neutral,
        )
        dc = self.dixon_coles.predict(
            history, home_team, away_team, features=features, before_date=ref
        )
        logistic = self.logistic.predict_match(
            history,
            home_team,
            away_team,
            phase=phase,
            is_neutral=is_neutral,
        )

        dw = self.dixon_coles_weight
        lw = self.logistic_weight
        probs = {
            "1": dw * dc.prob_home + lw * logistic.prob_home,
            "X": dw * dc.prob_draw + lw * logistic.prob_draw,
            "2": dw * dc.prob_away + lw * logistic.prob_away,
        }
        total = probs["1"] + probs["X"] + probs["2"]
        return {k: v / total for k, v in probs.items()}
