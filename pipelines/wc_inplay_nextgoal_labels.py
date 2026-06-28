"""Pipeline de labels reais de próximo gol para treino do GBM in-play.

Lê live_ticks.parquet, computa look-ahead de 10 min dentro de cada partida
para determinar se houve gol (e de quem) no intervalo [t, t+10].

Labels:
  0 = sem gol no intervalo
  1 = primeiro gol do home no intervalo
  2 = primeiro gol do away no intervalo

CLI: build-nextgoal-labels [--retrain] [--window N]
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel
from pipelines.wc_intensity_profile import default_intensity_profile

logger = logging.getLogger(__name__)

NEXTGOAL_DATASET_PATH = settings.lake_root / "silver" / "inplay" / "nextgoal_labels.parquet"
WINDOW_MINUTES = 10


# ---------------------------------------------------------------------------
# Features helpers
# ---------------------------------------------------------------------------

def _nhpp_remaining_fraction(minute: int) -> float:
    """Fração NHPP de intensidade restante a partir do minuto dado."""
    profile = default_intensity_profile()
    total = sum(b.weight * b.duration for b in profile)
    cumul = sum(
        b.weight * (min(b.end_min, minute) - b.start_min)
        for b in profile
        if b.start_min < minute
    )
    return max(0.0, 1.0 - cumul / total)


def _lambda_approx(row: pd.Series, remaining_frac: float, minute: int) -> tuple[float, float]:
    """Aproxima λ_remaining por minuto de home e away via implied odds h2h."""
    try:
        from models.wc_market_shrinkage import market_prob_to_lambda

        p1 = float(row.get("h2h_odd_1") or 0)
        px = float(row.get("h2h_odd_x") or 0)
        p2 = float(row.get("h2h_odd_2") or 0)
        if p1 > 0 and px > 0 and p2 > 0:
            lh, la = market_prob_to_lambda(p1, px, p2)
            remaining_time = max(90 - minute, 1)
            return (lh * remaining_frac / remaining_time,
                    la * remaining_frac / remaining_time)
    except Exception:
        pass
    remaining_time = max(90 - minute, 1)
    return (1.3 * remaining_frac / remaining_time,
            1.1 * remaining_frac / remaining_time)


# ---------------------------------------------------------------------------
# Label extraction
# ---------------------------------------------------------------------------

def build_nextgoal_labels(
    ticks: pd.DataFrame,
    window_minutes: int = WINDOW_MINUTES,
) -> pd.DataFrame:
    """Constrói dataset com labels de próximo gol e features GBM.

    Args:
        ticks: DataFrame de live_ticks.parquet.
        window_minutes: janela de look-ahead em minutos.

    Returns:
        DataFrame com GBM_FEATURES + 'label' + metadados.
    """
    if ticks.empty:
        return pd.DataFrame()

    df = ticks.copy()
    for col in ("event_id", "minute", "home_score", "away_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["event_id", "minute", "home_score", "away_score"])

    sort_keys = ["event_id", "minute"]
    if "captured_at" in df.columns:
        sort_keys.append("captured_at")
    df = df.sort_values(sort_keys, na_position="last").reset_index(drop=True)

    rows: list[dict[str, Any]] = []

    for event_id, group in df.groupby("event_id"):
        group = group.reset_index(drop=True)
        minutes = group["minute"].values.astype(float)
        home_scores = group["home_score"].values.astype(float)
        away_scores = group["away_score"].values.astype(float)

        for i in range(len(group)):
            minute = float(minutes[i])
            if minute >= 90:
                continue

            home_sc = int(home_scores[i])
            away_sc = int(away_scores[i])

            # Look-ahead em [minute+1, minute+window]
            ahead_mask = (minutes > minute) & (minutes <= minute + window_minutes)
            ahead_h = home_scores[ahead_mask]
            ahead_a = away_scores[ahead_mask]

            label = 0
            if len(ahead_h) > 0:
                # Detectar primeiro tick onde placar mudou
                for j in range(len(ahead_h)):
                    dh = int(ahead_h[j]) - home_sc
                    da = int(ahead_a[j]) - away_sc
                    if dh > 0 or da > 0:
                        if dh > 0 and da == 0:
                            label = 1
                        elif da > 0 and dh == 0:
                            label = 2
                        else:
                            # Ambos: usar proporção de lambda como desempate
                            label = 1 if dh >= da else 2
                        break

            # Features
            remaining_frac = _nhpp_remaining_fraction(int(minute))
            row_data = group.iloc[i]
            lh, la = _lambda_approx(row_data, remaining_frac, int(minute))
            goal_diff = home_sc - away_sc

            # Hawkes: taxa de gols nos últimos 10 min como proxy
            recent_mask = (minutes >= minute - 10) & (minutes < minute)
            if recent_mask.any():
                first_recent_idx = np.where(recent_mask)[0][0]
                recent_home_goals = max(0, home_sc - int(home_scores[first_recent_idx]))
                recent_away_goals = max(0, away_sc - int(away_scores[first_recent_idx]))
            else:
                recent_home_goals = 0
                recent_away_goals = 0

            hawkes_h = float(recent_home_goals) * 0.08 + 0.3 * lh
            hawkes_a = float(recent_away_goals) * 0.08 + 0.3 * la

            late_factor = max(0.0, (minute - 75) / 15.0)
            momentum_h = max(0.5, 1.0 + 0.05 * goal_diff - 0.1 * late_factor)
            momentum_a = max(0.5, 1.0 - 0.05 * goal_diff - 0.1 * late_factor)

            rows.append({
                "event_id": int(event_id),
                "minute": int(minute),
                "label": label,
                # GBM_FEATURES
                "minute_norm": minute / 90.0,
                "home_score_partial": home_sc,
                "away_score_partial": away_sc,
                "goal_diff": goal_diff,
                "remaining_fraction": remaining_frac,
                "home_lambda_remaining": round(lh, 4),
                "away_lambda_remaining": round(la, 4),
                "home_red_cards": int(row_data.get("home_red_cards") or 0),
                "away_red_cards": int(row_data.get("away_red_cards") or 0),
                "home_corners": int(row_data.get("home_corners") or 0),
                "away_corners": int(row_data.get("away_corners") or 0),
                "hawkes_intensity_home": round(hawkes_h, 4),
                "hawkes_intensity_away": round(hawkes_a, 4),
                "momentum_home_factor": round(momentum_h, 4),
                "momentum_away_factor": round(momentum_a, 4),
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Persisted dataset
# ---------------------------------------------------------------------------

def save_nextgoal_dataset(df: pd.DataFrame, path: Path | None = None) -> Path:
    path = path or NEXTGOAL_DATASET_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return path


def load_nextgoal_dataset(path: Path | None = None) -> pd.DataFrame:
    path = path or NEXTGOAL_DATASET_PATH
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


# ---------------------------------------------------------------------------
# GBM training from real labels
# ---------------------------------------------------------------------------

def train_gbm_from_real_labels(
    df: pd.DataFrame,
    val_fraction: float = 0.2,
    n_estimators: int = 400,
    seed: int = 42,
) -> dict[str, Any]:
    """Treina GBM a partir dos labels reais do look-ahead.

    Split temporal: últimos val_fraction% dos ticks como validação.

    Returns:
        Dict com métricas e path do artefato salvo.
    """
    if df.empty or "label" not in df.columns:
        return {"error": "dataset vazio ou sem label"}

    missing = [f for f in GBM_FEATURES if f not in df.columns]
    if missing:
        return {"error": f"features ausentes: {missing}"}

    X = df[GBM_FEATURES].values.astype(np.float64)
    y = df["label"].values.astype(np.int64)

    n = len(df)
    val_start = int(n * (1 - val_fraction))
    X_train, y_train = X[:val_start], y[:val_start]
    X_val, y_val = X[val_start:], y[val_start:]

    model = InPlayGBMModel(window_minutes=WINDOW_MINUTES)
    metrics = model.fit(
        X_train, y_train,
        eval_X=X_val if len(X_val) > 0 else None,
        eval_y=y_val if len(y_val) > 0 else None,
        n_estimators=n_estimators,
        seed=seed,
    )

    path = model.save()

    label_counts = {
        "no_goal": int((y == 0).sum()),
        "home_goal": int((y == 1).sum()),
        "away_goal": int((y == 2).sum()),
    }
    importance = dict(
        sorted(model.feature_importance().items(), key=lambda x: -x[1])[:8]
    )

    return {
        **metrics,
        "artifact_path": str(path),
        "n_train": len(X_train),
        "n_val": len(X_val),
        "label_dist": label_counts,
        "top_features": importance,
    }


# ---------------------------------------------------------------------------
# Pipeline entrypoint
# ---------------------------------------------------------------------------

def run_nextgoal_pipeline(
    retrain: bool = False,
    window_minutes: int = WINDOW_MINUTES,
) -> dict[str, Any]:
    """Pipeline completo: lê ticks → labels → (opcional) treina GBM.

    Args:
        retrain: se True, treina mesmo que o modelo já exista.
        window_minutes: janela de look-ahead.

    Returns:
        Dict com resultado do pipeline.
    """
    from ingest.superbet.live_ticks import live_ticks_path

    ticks_path = live_ticks_path()
    if not ticks_path.exists():
        return {"error": f"live_ticks ausente: {ticks_path}"}

    ticks = pd.read_parquet(ticks_path)
    n_events = int(ticks["event_id"].nunique()) if "event_id" in ticks.columns else 0
    logger.info("ticks_carregados", n_ticks=len(ticks), n_events=n_events)

    df = build_nextgoal_labels(ticks, window_minutes=window_minutes)
    if df.empty:
        return {"error": "Sem labels extraídas dos ticks (partidas insuficientes)"}

    dataset_path = save_nextgoal_dataset(df)
    logger.info("dataset_salvo", n_amostras=len(df), path=str(dataset_path))

    artifact_path = settings.lake_root / "artifacts" / "inplay_gbm.pkl"
    if retrain or not artifact_path.exists():
        metrics = train_gbm_from_real_labels(df)
        metrics["dataset_path"] = str(dataset_path)
        metrics["n_events"] = n_events
        return metrics

    return {
        "dataset_path": str(dataset_path),
        "n_samples": len(df),
        "n_events": n_events,
        "label_dist": {
            "no_goal": int((df["label"] == 0).sum()),
            "home_goal": int((df["label"] == 1).sum()),
            "away_goal": int((df["label"] == 2).sum()),
        },
        "retrain": False,
        "hint": "Use --retrain para forçar retreino do GBM.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Constrói labels de próximo gol e (opcionalmente) retreina GBM"
    )
    parser.add_argument("--retrain", action="store_true",
                        help="Retreinar GBM após construir labels")
    parser.add_argument("--window", type=int, default=WINDOW_MINUTES,
                        help="Janela de look-ahead em minutos")
    parser.add_argument("--json", action="store_true", help="Output em JSON")
    args = parser.parse_args()

    result = run_nextgoal_pipeline(retrain=args.retrain, window_minutes=args.window)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
