"""Pipeline de retreino do GBM in-play com dataset enriquecido pelo feedback real.

Fase 4 — Feedback Loop:
1. Lê silver_bet_reconciliation (apostas reais com snapshot do modelo).
2. Constrói features no formato do GBM (Fase 3.3).
3. Combina com dataset sintético do GBM com peso menor.
4. Re-treina com walk-forward e calibrador Platt.
5. Salva artefato versionado SE Brier delta < threshold.

Gate de aceitação: novo artefato só substitui o atual se
    Brier_holdout_novo < Brier_holdout_atual - 0.002

CLI: retrain-with-feedback --user jamarorn --min-confidence 0.7
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import structlog

from config import settings
from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel
from pipelines.user_bet_reconciliation import load_reconciliation

log = structlog.get_logger()

BRIER_DELTA_THRESHOLD = 0.002


@dataclass
class FeedbackRetrainResult:
    """Resultado do retreino com feedback."""

    n_feedback_examples: int
    n_synthetic_examples: int
    n_tick_examples: int
    brier_old: float
    brier_new: float
    brier_delta: float
    accepted: bool
    artifact_path: str | None
    timestamp: str


def build_feedback_features(
    user_id: str,
    *,
    min_confidence: float = 0.7,
) -> tuple[np.ndarray, np.ndarray]:
    """Extrai features e targets das apostas reconciliadas com alta confiança."""
    df = load_reconciliation(user_id)
    if df.empty:
        return np.array([]), np.array([])

    df_valid = df[
        (df["match_confidence"].fillna(0) >= min_confidence)
        & df["event_id"].notna()
        & df["match_minute"].notna()
    ].copy()

    if df_valid.empty:
        return np.array([]), np.array([])

    n = len(df_valid)
    X = np.zeros((n, len(GBM_FEATURES)))
    y = np.zeros(n, dtype=np.int64)

    for idx, (_, row) in enumerate(df_valid.iterrows()):
        minute = int(row.get("match_minute", 0))
        hs = int(row.get("home_score", 0)) if pd.notna(row.get("home_score")) else 0
        as_ = int(row.get("away_score", 0)) if pd.notna(row.get("away_score")) else 0

        X[idx, 0] = minute / 90  # minute_norm
        X[idx, 1] = float(hs)
        X[idx, 2] = float(as_)
        X[idx, 3] = float(hs - as_)

        # Fração NHPP restante: heurística simples
        X[idx, 4] = max(0, 90 - minute) / 90  # remaining_fraction

        p_h = row.get("prob_final_home")
        p_a = row.get("prob_final_away")
        X[idx, 5] = float(p_h) * 0.03 if pd.notna(p_h) else 0.015
        X[idx, 6] = float(p_a) * 0.03 if pd.notna(p_a) else 0.012

        # Cards: assumir 0 (não temos no snapshot in-play básico)
        X[idx, 7] = 0.0
        X[idx, 8] = 0.0

        # Corners: do snapshot se disponível, senão 0
        X[idx, 9] = 0.0
        X[idx, 10] = 0.0

        # Hawkes intensity: usar generosity como proxy
        gen_h = float(row.get("model_generosity_home", 0.5))
        gen_a = float(row.get("model_generosity_away", 0.5))
        X[idx, 11] = gen_h
        X[idx, 12] = gen_a

        # Momentum factors
        goal_diff = hs - as_
        late = max(0, minute - 75) / 15.0
        X[idx, 13] = 1.0 + 0.05 * goal_diff - 0.1 * late
        X[idx, 14] = 1.0 - 0.05 * goal_diff - 0.1 * late

        # Target: como não sabemos qual mercado a aposta atinge, inferimos:
        # - Se won=True E home na frente → home marcou (target=1)
        # - Se won=True E away na frente → away marcou (target=2)
        # - Se won=False → assumimos no_goal (target=0)
        # Heurística limitada — em produção real, precisaria do market explícito.
        won = bool(row.get("won", False))
        if won:
            if (hs - as_) > 0:
                y[idx] = 1
            elif (hs - as_) < 0:
                y[idx] = 2
            else:
                y[idx] = 0  # empate: sem lado claro → no_goal
        else:
            y[idx] = 0

    return X, y


def evaluate_brier(
    model: InPlayGBMModel,
    X: np.ndarray,
    y: np.ndarray,
) -> float:
    """Calcula Brier multiclasse no dataset."""
    if X.size == 0:
        return float("inf")
    if not model.is_fitted:
        return float("inf")

    preds = model.predict(X)
    probs = np.array([
        [p.prob_no_goal, p.prob_goal_home, p.prob_goal_away]
        for p in preds
    ])
    # Brier multiclasse: Σ (p_pred - y_onehot)²
    y_onehot = np.zeros((len(y), 3))
    for i, target in enumerate(y):
        y_onehot[i, target] = 1
    brier = float(np.mean(np.sum((probs - y_onehot) ** 2, axis=1)))
    return brier


def retrain_with_feedback(
    user_id: str = "jamarorn",
    min_confidence: float = 0.7,
    feedback_weight: float = 3.0,
    seed: int = 42,
    accept_threshold: float = BRIER_DELTA_THRESHOLD,
) -> FeedbackRetrainResult:
    """Re-treina o GBM combinando dataset sintético + feedback do usuário.

    Args:
        user_id: usuário cuja reconciliação alimenta o retreino.
        min_confidence: confidence mínima para usar exemplo do feedback.
        feedback_weight: multiplicador do peso dos exemplos reais (sample_weight).
        seed: reprodutibilidade.
        accept_threshold: Brier delta mínimo para aceitar substituição.

    Returns:
        FeedbackRetrainResult com decisão e métricas.
    """
    log.info("feedback_retrain_started", user_id=user_id)

    # 1. Carregar feedback (CSV reconciliado)
    X_fb, y_fb = build_feedback_features(user_id, min_confidence=min_confidence)
    n_fb = len(X_fb)

    # 1b. Exemplos de ticks ao vivo com placar final (gold)
    from pipelines.inplay_synthetic_feedback import build_synthetic_gbm_from_match_states

    X_ms, y_ms = build_synthetic_gbm_from_match_states()
    n_ms = len(X_ms)

    log.info("feedback_examples_loaded", n_feedback=n_fb, n_ticks=n_ms)

    min_ticks = settings.inplay_synthetic_min_examples
    if n_fb == 0 and n_ms < min_ticks:
        log.warning("feedback_retrain_skipped_no_data")
        return FeedbackRetrainResult(
            n_feedback_examples=0,
            n_synthetic_examples=0,
            n_tick_examples=n_ms,
            brier_old=0.0,
            brier_new=0.0,
            brier_delta=0.0,
            accepted=False,
            artifact_path=None,
            timestamp=datetime.now().isoformat(),
        )

    # Holdout: feedback real ou 20% dos ticks
    if n_fb > 0:
        X_hold, y_hold = X_fb, y_fb
    else:
        split = max(1, int(n_ms * 0.2))
        X_hold, y_hold = X_ms[-split:], y_ms[-split:]
        X_ms, y_ms = X_ms[:-split], y_ms[:-split]
        n_ms = len(X_ms)
        log.info("feedback_holdout_from_ticks", n_holdout=len(X_hold))

    # 2. Carregar dataset sintético existente
    from pipelines.wc_inplay_gbm_train import build_gbm_dataset
    from pipelines.wc_build_timeline import build_timeline_from_fixtures

    timeline = build_timeline_from_fixtures(min_season=2018, max_season=2026)
    if timeline.empty:
        log.warning("feedback_retrain_no_timeline")
        return FeedbackRetrainResult(
            n_feedback_examples=n_fb,
            n_synthetic_examples=0,
            n_tick_examples=n_ms,
            brier_old=0.0,
            brier_new=0.0,
            brier_delta=0.0,
            accepted=False,
            artifact_path=None,
            timestamp=datetime.now().isoformat(),
        )

    if len(timeline) > 5000:
        timeline = timeline.sample(n=5000, random_state=seed)

    X_syn, y_syn = build_gbm_dataset(timeline)
    n_syn = len(X_syn)
    log.info("synthetic_examples_loaded", n=n_syn)

    tick_weight = settings.inplay_synthetic_tick_weight
    parts_x: list[np.ndarray] = [X_syn]
    parts_y: list[np.ndarray] = [y_syn]
    parts_w: list[np.ndarray] = [np.ones(n_syn)]
    if n_ms > 0:
        parts_x.append(X_ms)
        parts_y.append(y_ms)
        parts_w.append(np.full(n_ms, tick_weight))
    if n_fb > 0:
        parts_x.append(X_fb)
        parts_y.append(y_fb)
        parts_w.append(np.full(n_fb, feedback_weight))

    X_combined = np.vstack(parts_x)
    y_combined = np.concatenate(parts_y)
    weights = np.concatenate(parts_w)

    # 4. Avaliar modelo atual no holdout
    old_model = InPlayGBMModel.load()
    brier_old = evaluate_brier(old_model, X_hold, y_hold) if old_model.is_fitted else 1.0
    log.info("brier_old_baseline", brier=brier_old)

    # 5. Treinar novo modelo
    new_model = InPlayGBMModel(window_minutes=10)
    try:
        import lightgbm as lgb
        params = {
            "objective": "multiclass",
            "num_class": 3,
            "metric": "multi_logloss",
            "n_estimators": 200,
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_child_samples": 30,
            "reg_lambda": 1.0,
            "random_state": seed,
            "verbose": -1,
            "n_jobs": -1,
        }
        new_model._model = lgb.LGBMClassifier(**params)
        X_train_df = InPlayGBMModel._features_to_frame(X_combined)
        new_model._model.fit(X_train_df, y_combined, sample_weight=weights)
        new_model._fitted = True
    except Exception as exc:
        log.error("feedback_retrain_fit_failed", error=str(exc))
        return FeedbackRetrainResult(
            n_feedback_examples=n_fb,
            n_synthetic_examples=n_syn,
            n_tick_examples=n_ms,
            brier_old=brier_old,
            brier_new=brier_old,
            brier_delta=0.0,
            accepted=False,
            artifact_path=None,
            timestamp=datetime.now().isoformat(),
        )

    # 6. Avaliar novo modelo no holdout
    brier_new = evaluate_brier(new_model, X_hold, y_hold)
    delta = brier_old - brier_new
    accepted = delta >= accept_threshold

    log.info(
        "feedback_retrain_evaluated",
        brier_old=round(brier_old, 4),
        brier_new=round(brier_new, 4),
        delta=round(delta, 4),
        accepted=accepted,
    )

    artifact_path = None
    if accepted:
        # 7. Salvar versionado e atualizar default
        version = datetime.now().strftime("%Y%m%dT%H%M%S")
        versioned = (
            Path(settings.lake_root) / "artifacts" /
            f"inplay_gbm_feedback_v{version}.pkl"
        )
        new_model.save(versioned)
        new_model.save()  # também substitui o default
        artifact_path = str(versioned)
        log.info("feedback_artifact_saved", path=artifact_path)

        # Manifest com metadados
        manifest = {
            "version": version,
            "user_id": user_id,
            "n_feedback": n_fb,
            "n_synthetic": n_syn,
            "n_ticks": n_ms,
            "feedback_weight": feedback_weight,
            "brier_old": brier_old,
            "brier_new": brier_new,
            "brier_delta": delta,
            "min_confidence": min_confidence,
        }
        manifest_path = versioned.with_suffix(".json")
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))

    return FeedbackRetrainResult(
        n_feedback_examples=n_fb,
        n_synthetic_examples=n_syn,
        n_tick_examples=n_ms,
        brier_old=brier_old,
        brier_new=brier_new,
        brier_delta=delta,
        accepted=accepted,
        artifact_path=artifact_path,
        timestamp=datetime.now().isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-treina o GBM in-play com feedback real do usuário (Fase 4)."
    )
    parser.add_argument("--user", default="jamarorn", help="user_id da reconciliação")
    parser.add_argument(
        "--min-confidence", type=float, default=0.7,
        help="confidence mínima para usar exemplo no retreino",
    )
    parser.add_argument(
        "--feedback-weight", type=float, default=3.0,
        help="peso dos exemplos reais relativo ao sintético",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = retrain_with_feedback(
        user_id=args.user,
        min_confidence=args.min_confidence,
        feedback_weight=args.feedback_weight,
        seed=args.seed,
    )

    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0 if result.accepted else 0  # não falha — gate é informativo


if __name__ == "__main__":
    sys.exit(main())
