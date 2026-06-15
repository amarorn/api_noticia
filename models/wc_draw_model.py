"""Modelo two-stage: P(empate) dedicado e redistribuição condicional de 1 vs 2."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from pipelines.wc_group_pressure import GroupPressure
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import WcMatchFeatures, row_group_name


DRAW_FEATURE_NAMES = [
    "elo_closeness",
    "abs_elo_diff_norm",
    "phase_knockout",
    "is_neutral",
    "h2h_draw_rate",
    "wc_draw_rate_diff",
    "home_must_win",
    "away_must_win",
    "secured_diff",
    "group_matchday_norm",
]


@dataclass
class DrawModelMetrics:
    train_size: int
    draw_rate: float
    holdout_accuracy: float | None = None


def _wc_draw_rates(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    before_date: datetime | None,
) -> tuple[float, float]:
    df = fixtures_df.copy()
    if before_date is not None:
        cutoff = pd.to_datetime(before_date, utc=True)
        df = df[pd.to_datetime(df["match_date"], utc=True) < cutoff]
    neutral = df[df.get("is_neutral", True).astype(bool) if "is_neutral" in df.columns else True]
    if neutral.empty:
        neutral = df

    def rate(team: str) -> float:
        games = neutral[
            (neutral["home_team"] == team) | (neutral["away_team"] == team)
        ]
        if games.empty:
            return 0.2
        draws = sum(
            1
            for _, r in games.iterrows()
            if int(r["home_score"]) == int(r["away_score"])
        )
        return draws / len(games)

    return rate(home_team), rate(away_team)


def draw_features_to_vector(
    features: WcMatchFeatures,
    pressure: GroupPressure,
    *,
    home_draw_rate: float,
    away_draw_rate: float,
) -> list[float]:
    closeness = 1.0 / (1.0 + abs(features.elo_diff) / 120.0)
    return [
        closeness,
        min(abs(features.elo_diff) / 400.0, 2.0),
        float(features.phase_knockout),
        float(features.is_neutral),
        features.h2h_draws / max(features.h2h_total, 1),
        home_draw_rate - away_draw_rate,
        pressure.home_must_win,
        pressure.away_must_win,
        pressure.home_secured - pressure.away_secured,
        min(pressure.group_matchday / 3.0, 1.0),
    ]


def apply_two_stage_probs(
    probs: dict[str, float],
    p_draw: float,
    *,
    blend: float,
    knockout: bool,
) -> dict[str, float]:
    hp = get_wc_hyperparams()
    p_draw_adj = p_draw
    if knockout:
        p_draw_adj *= hp.knockout_draw_discount

    p_x = blend * p_draw_adj + (1.0 - blend) * probs["X"]
    p_x = min(max(p_x, 0.05), 0.42)

    non_draw = probs["1"] + probs["2"]
    if non_draw < 1e-9:
        p1_cond = 0.5
    else:
        p1_cond = probs["1"] / non_draw

    rem = 1.0 - p_x
    return {"1": rem * p1_cond, "X": p_x, "2": rem * (1.0 - p1_cond)}


def resolve_wc_outcome(
    probs: dict[str, float],
    *,
    phase: str = "group",
    draw_pick_min_prob: float | None = None,
    draw_balance_gap: float | None = None,
    draw_competitive_margin: float | None = None,
) -> str:
    """Escolhe palpite 1/X/2 a partir das probabilidades calibradas.

    Além do argmax simples, prevê empate em jogos equilibrados de fase de grupos
    quando P(X) é competitiva e a diferença entre mandante e visitante é pequena.
    """
    hp = get_wc_hyperparams()
    min_px = draw_pick_min_prob if draw_pick_min_prob is not None else hp.draw_pick_min_prob
    gap = draw_balance_gap if draw_balance_gap is not None else hp.draw_balance_gap
    margin = (
        draw_competitive_margin
        if draw_competitive_margin is not None
        else hp.draw_competitive_margin
    )
    knockout = phase not in ("group",)

    p1, px, p2 = probs["1"], probs["X"], probs["2"]
    favorite_gap = abs(p1 - p2)
    favorite = max(p1, p2)

    if px >= favorite:
        return "X"

    if not knockout and px >= min_px:
        if favorite_gap <= gap:
            return "X"
        if px >= favorite - margin:
            return "X"

    return max(probs, key=probs.get)  # type: ignore[return-value]


class WcDrawModel:
    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.model = LogisticRegression(
            C=0.5,
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
            solver="lbfgs",
        )
        self._fitted = False
        self.metrics: DrawModelMetrics | None = None

    def fit(
        self,
        *,
        feature_rows: list[list[float]],
        labels: list[int],
    ) -> DrawModelMetrics:
        if len(feature_rows) < 40:
            raise ValueError(f"Dados insuficientes para modelo de empate ({len(feature_rows)})")

        x_scaled = self.scaler.fit_transform(feature_rows)
        self.model.fit(x_scaled, labels)
        self._fitted = True

        draw_rate = sum(labels) / len(labels)
        metrics = DrawModelMetrics(train_size=len(labels), draw_rate=round(draw_rate, 4))
        self.metrics = metrics
        return metrics

    def predict_draw_prob(
        self,
        feature_vector: list[float],
    ) -> float:
        if not self._fitted:
            return 0.22
        x = self.scaler.transform([feature_vector])[0]
        proba = self.model.predict_proba([x])[0]
        classes = list(self.model.classes_)
        if 1 in classes:
            return float(proba[classes.index(1)])
        return float(proba[-1])


def build_draw_training_rows(
    fixtures_df: pd.DataFrame,
    train_df: pd.DataFrame,
) -> tuple[list[list[float]], list[int]]:
    from pipelines.wc_stats import build_match_features, group_pressure_from_features, precompute_elo_timeline

    elo_timeline = precompute_elo_timeline(fixtures_df)
    x_rows: list[list[float]] = []
    y_rows: list[int] = []

    for _, row in train_df.iterrows():
        before = row["match_date"]
        gcol = row_group_name(row)
        feats = build_match_features(
            fixtures_df,
            row["home_team"],
            row["away_team"],
            before_date=before,
            phase=row.get("phase", "group"),
            is_neutral=bool(row.get("is_neutral", True)),
            season=int(row["season"]),
            group_name=gcol if gcol is not None and not pd.isna(gcol) else None,
            elo_timeline=elo_timeline,
        )
        pressure = group_pressure_from_features(feats)
        h_rate, a_rate = _wc_draw_rates(
            fixtures_df, row["home_team"], row["away_team"], before
        )
        x_rows.append(
            draw_features_to_vector(feats, pressure, home_draw_rate=h_rate, away_draw_rate=a_rate)
        )
        y_rows.append(1 if row["label"] == "X" else 0)

    return x_rows, y_rows
