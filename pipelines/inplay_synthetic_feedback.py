"""Exemplos sintéticos GBM a partir de ticks ao vivo com placar final (gold).

Complementa o feedback CSV: cada tick rotulado em ``match_states.parquet``
vira exemplo de treino para o GBM in-play.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from models.wc_inplay_gbm import GBM_FEATURES
from pipelines.inplay_match_states import MATCH_STATES_PATH


def _cell_float(row: pd.Series, *keys: str, default: float = 0.0) -> float:
    """Lê célula numérica tolerando NA do pandas (sem ``or`` ambíguo)."""
    for key in keys:
        if key not in row.index:
            continue
        val = row[key]
        if pd.isna(val):
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return default


def _cell_int(row: pd.Series, key: str, default: int = 0) -> int:
    if key not in row.index or pd.isna(row[key]):
        return default
    try:
        return int(row[key])
    except (TypeError, ValueError):
        return default


def _target_from_remaining(remaining_home: int, remaining_away: int) -> int:
    """Target multiclasse GBM: 0=sem gol restante, 1=home, 2=away."""
    if remaining_home <= 0 and remaining_away <= 0:
        return 0
    if remaining_home > 0 and remaining_away == 0:
        return 1
    if remaining_away > 0 and remaining_home == 0:
        return 2
    return 1 if remaining_home >= remaining_away else 2


def build_synthetic_gbm_from_match_states(
    *,
    max_examples: int | None = 5000,
    min_minute: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Features/targets a partir de ``silver/inplay/match_states.parquet``."""
    if not MATCH_STATES_PATH.exists():
        return np.array([]), np.array([])

    df = pd.read_parquet(MATCH_STATES_PATH)
    if df.empty:
        return np.array([]), np.array([])

    labeled = df[
        df["y_final"].notna()
        & df["home_score_final"].notna()
        & df["away_score_final"].notna()
        & df["minute"].notna()
    ].copy()
    if labeled.empty:
        return np.array([]), np.array([])

    labeled["minute"] = pd.to_numeric(labeled["minute"], errors="coerce").fillna(0).astype(int)
    labeled = labeled[labeled["minute"] >= min_minute]
    if labeled.empty:
        return np.array([]), np.array([])

    if max_examples and len(labeled) > max_examples:
        labeled = labeled.sample(n=max_examples, random_state=42)

    n = len(labeled)
    X = np.zeros((n, len(GBM_FEATURES)))
    y = np.zeros(n, dtype=np.int64)

    for idx, (_, row) in enumerate(labeled.iterrows()):
        minute = int(row["minute"])
        hs = _cell_int(row, "home_score")
        aw = _cell_int(row, "away_score")
        hs_f = int(row["home_score_final"])
        aw_f = int(row["away_score_final"])

        X[idx, 0] = minute / 90
        X[idx, 1] = float(hs)
        X[idx, 2] = float(aw)
        X[idx, 3] = float(hs - aw)
        X[idx, 4] = max(0, 90 - minute) / 90

        p_h = row.get("prob_final_home")
        p_a = row.get("prob_final_away")
        X[idx, 5] = float(p_h) * 0.03 if pd.notna(p_h) else 0.015
        X[idx, 6] = float(p_a) * 0.03 if pd.notna(p_a) else 0.012

        X[idx, 7] = _cell_float(row, "home_red_cards", "n_red_cards_ss")
        X[idx, 8] = _cell_float(row, "away_red_cards")
        X[idx, 9] = _cell_float(row, "home_corners")
        X[idx, 10] = _cell_float(row, "away_corners")

        hxg = row.get("home_xg")
        if pd.notna(hxg) and float(hxg) > 0:
            X[idx, 5] = float(hxg) * 0.5
        ayxg = row.get("away_xg")
        if pd.notna(ayxg) and float(ayxg) > 0:
            X[idx, 6] = float(ayxg) * 0.5

        gen_h = row.get("model_generosity_home")
        gen_a = row.get("model_generosity_away")
        X[idx, 11] = float(gen_h) if pd.notna(gen_h) else 0.5
        X[idx, 12] = float(gen_a) if pd.notna(gen_a) else 0.5

        goal_diff = hs - aw
        late = max(0, minute - 75) / 15.0
        X[idx, 13] = 1.0 + 0.05 * goal_diff - 0.1 * late
        X[idx, 14] = 1.0 - 0.05 * goal_diff - 0.1 * late

        y[idx] = _target_from_remaining(hs_f - hs, aw_f - aw)

    return X, y


def count_synthetic_examples() -> int:
    X, _ = build_synthetic_gbm_from_match_states(max_examples=None)
    return len(X)


__all__ = [
    "build_synthetic_gbm_from_match_states",
    "count_synthetic_examples",
]
