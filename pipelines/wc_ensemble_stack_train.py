"""Treina o meta-learner de stacking do ensemble in-play.

Usa match_states.parquet (silver) como dataset de treino:
  - prob_final_home/draw/away  → componente "model" (tratada como Poisson)
  - h2h_odd_1/x/2             → implied market probs
  - minute, home_score - away_score → contexto
  - y_final                   → target

Hawkes e GBM recebem 1/3 (prior uniforme) quando não disponíveis no parquet.
O meta-learner aprende a combinar model + market otimizando LogLoss.

CLI: train-ensemble-stack [--min-samples N] [--C float]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from models.wc_ensemble_stack import (
    StackedEnsemble,
    _META_FEATURES,
    build_meta_features,
    invalidate_stack_cache,
)
from pipelines.inplay_match_states import MATCH_STATES_PATH

logger = logging.getLogger(__name__)

_MIN_SAMPLES = 200


def _implied_probs(row: pd.Series) -> tuple[float, float, float] | None:
    """Extrai probabilidades implícitas das odds h2h (sem margem)."""
    try:
        p1 = float(row.get("h2h_odd_1") or 0)
        px = float(row.get("h2h_odd_x") or 0)
        p2 = float(row.get("h2h_odd_2") or 0)
        if p1 <= 0 or px <= 0 or p2 <= 0:
            return None
        total = p1 + px + p2
        return p1 / total, px / total, p2 / total
    except Exception:
        return None


def build_stack_dataset(
    match_states: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    """Constrói DataFrame de meta-features e série de labels para treino.

    Args:
        match_states: match_states.parquet enriquecido com y_final.

    Returns:
        (X_meta, y) onde y ∈ {"1", "X", "2"}.
    """
    df = match_states.copy()
    df = df[df["y_final"].notna()].reset_index(drop=True)

    if df.empty:
        return pd.DataFrame(), pd.Series(dtype=str)

    rows: list[dict[str, float]] = []
    labels: list[str] = []

    for _, row in df.iterrows():
        minute = float(row.get("minute") or 0)
        home_sc = float(row.get("home_score") or 0)
        away_sc = float(row.get("away_score") or 0)
        y = str(row["y_final"])

        # Componente "model" (Poisson proxy)
        p1_m = float(row.get("prob_final_home") or 1 / 3)
        px_m = float(row.get("prob_final_draw") or 1 / 3)
        p2_m = float(row.get("prob_final_away") or 1 / 3)
        tot_m = p1_m + px_m + p2_m
        if tot_m > 0:
            p1_m, px_m, p2_m = p1_m / tot_m, px_m / tot_m, p2_m / tot_m

        poisson_probs = {"1": p1_m, "X": px_m, "2": p2_m}

        # Componente market (implied odds)
        market_implied = _implied_probs(row)
        market_probs: dict[str, float] | None = None
        if market_implied:
            market_probs = {"1": market_implied[0], "X": market_implied[1], "2": market_implied[2]}

        # Contexto
        remaining_frac = max(0.0, (90 - minute) / 90)

        meta = build_meta_features(
            poisson_probs=poisson_probs,
            hawkes_probs=None,   # não disponível no parquet histórico
            gbm_probs=None,      # idem
            market_probs=market_probs,
            minute=minute,
            score_diff=home_sc - away_sc,
            remaining_frac=remaining_frac,
        )
        rows.append(meta)
        labels.append(y)

    X = pd.DataFrame(rows, columns=_META_FEATURES)
    y = pd.Series(labels, name="y_final")
    return X, y


def train_stack(
    min_samples: int = _MIN_SAMPLES,
    C: float = 1.0,
    seed: int = 42,
    states_path: Path | None = None,
) -> dict[str, Any]:
    """Treina o meta-learner e salva o artefato.

    Args:
        min_samples: mínimo de amostras para treinar (senão retorna erro).
        C: regularização do LogisticRegression.
        seed: reprodutibilidade.
        states_path: caminho alternativo para match_states.parquet.

    Returns:
        Dict com métricas e path do artefato.
    """
    path = states_path or MATCH_STATES_PATH
    if not path.exists():
        return {"error": f"match_states ausente: {path}"}

    states = pd.read_parquet(path)
    labeled = states[states["y_final"].notna()]
    if len(labeled) < min_samples:
        return {
            "error": f"Amostras insuficientes: {len(labeled)} < {min_samples}",
            "n_labeled": len(labeled),
        }

    X, y = build_stack_dataset(labeled)
    if X.empty:
        return {"error": "Dataset meta-features vazio após filtragem."}

    # Split temporal: últimos 20% para avaliação
    n_val = max(1, int(len(X) * 0.2))
    X_train, y_train = X.iloc[:-n_val], y.iloc[:-n_val]
    X_val, y_val = X.iloc[-n_val:], y.iloc[-n_val:]

    stack = StackedEnsemble()
    train_metrics = stack.fit(X_train, y_train, C=C, seed=seed)

    # Validação
    from sklearn.metrics import log_loss

    val_probs = np.array([
        list(stack.predict(row.to_dict()).values())
        for _, row in X_val.iterrows()
    ])
    from models.wc_ensemble_stack import _LABEL_MAP
    y_val_int = y_val.map(lambda x: _LABEL_MAP.get(str(x), 0)).values
    val_ll = float(log_loss(y_val_int, val_probs))

    artifact_path = stack.save()
    invalidate_stack_cache()

    logger.info(
        "ensemble_stack_treinado",
        n_train=len(X_train),
        n_val=n_val,
        train_ll=round(train_metrics["train_logloss"], 4),
        val_ll=round(val_ll, 4),
    )

    return {
        **train_metrics,
        "val_logloss": val_ll,
        "n_val": n_val,
        "artifact_path": str(artifact_path),
        "states_path": str(path),
        "C": C,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Treina stacking ensemble in-play")
    parser.add_argument("--min-samples", type=int, default=_MIN_SAMPLES)
    parser.add_argument("--C", type=float, default=1.0,
                        help="Regularização LogisticRegression (menor = mais regularização)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = train_stack(min_samples=args.min_samples, C=args.C)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
