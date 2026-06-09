"""Pipeline de treino walk-forward do LightGBM in-play.

Constrói o dataset de treino a partir da timeline de fixtures,
calcula targets multiclasse (quem marca no intervalo [t, t+Δ]),
e treina o modelo com validação temporal.

Walk-forward: treina em edições anteriores, valida na seguinte.
Ex: treina 2010–2018, valida 2022.

Spec: docs/specs/spec-fase-3-modelo-avancado.md § 5.2
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from models.wc_hawkes import HawkesGoalEvent, HawkesParameters, hawkes_intensity
from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel
from pipelines.wc_build_timeline import build_timeline_from_fixtures
from pipelines.wc_inplay_hawkes_fit import load_hawkes_params
from pipelines.wc_intensity_profile import default_intensity_profile


@dataclass
class GBMTrainResult:
    """Resultado do treino walk-forward do GBM."""

    train_logloss: float
    val_logloss: float
    train_accuracy: float
    val_accuracy: float
    n_train: int
    n_val: int
    feature_importance: dict[str, float]


def _nhpp_remaining_fraction(minute: int, match_minutes: int = 90) -> float:
    """Fração NHPP de gols restantes a partir do minuto."""
    profile = default_intensity_profile()
    total_weighted = sum(b.weight * b.duration for b in profile)
    cumul = 0.0
    for b in profile:
        start = b.start_min
        end = min(b.end_min, minute)
        if start < end:
            cumul += b.weight * (end - start)
    return 1.0 - (cumul / total_weighted)


def build_gbm_dataset(
    timeline_df: pd.DataFrame,
    window_minutes: int = 10,
    hawkes_params: HawkesParameters | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Constrói features X e target y para treino do GBM.

    Target multiclasse:
    - 0 = nenhum gol no intervalo [t, t+Δ]
    - 1 = próximo gol é do home
    - 2 = próximo gol é do away

    Como não temos minuto exato dos gols, usamos heurística:
    - Se remaining_goals_home > 0 E remaining_goals_away == 0: target=1
    - Se remaining_goals_away > 0 E remaining_goals_home == 0: target=2
    - Se ambos > 0: atribuímos proporcional (mais provável = target)
    - Se nenhum restante: target=0

    Para determinar se gol ocorre no intervalo [t, t+Δ], usamos
    a fração NHPP do intervalo × total de gols restantes.
    """
    if hawkes_params is None:
        hawkes_params = load_hawkes_params()

    n = len(timeline_df)
    X = np.zeros((n, len(GBM_FEATURES)))
    y = np.zeros(n, dtype=np.int64)

    match_minutes = 90

    for idx in range(n):
        row = timeline_df.iloc[idx]
        minute = int(row["minute"])
        hs_partial = int(row["home_score_partial"])
        as_partial = int(row["away_score_partial"])
        remaining_h = int(row["remaining_goals_home"])
        remaining_a = int(row["remaining_goals_away"])
        home_reds = int(row.get("home_red_cards", 0))
        away_reds = int(row.get("away_red_cards", 0))
        home_corners = int(row.get("home_corners", 0))
        away_corners = int(row.get("away_corners", 0))
        remaining_frac = float(row.get("remaining_fraction", 0.5))

        # Baselines por minuto (média WC ≈ 2.6 gols/jogo)
        mu_home = 1.4 / match_minutes
        mu_away = 1.2 / match_minutes

        # λ remaining per minute
        lambda_remaining_h = mu_home * remaining_frac * match_minutes / max(
            match_minutes - minute, 1
        )
        lambda_remaining_a = mu_away * remaining_frac * match_minutes / max(
            match_minutes - minute, 1
        )

        # Hawkes intensity (usando gols passados reconstruídos)
        past_goals = _reconstruct_past_goals(hs_partial, as_partial, minute)
        hawkes_h = hawkes_intensity(
            float(minute), past_goals, hawkes_params, mu_home, "home"
        )
        hawkes_a = hawkes_intensity(
            float(minute), past_goals, hawkes_params, mu_away, "away"
        )

        # Momentum (simplificado — sem import circular)
        goal_diff = hs_partial - as_partial
        late_factor = max(0, minute - 75) / 15.0
        momentum_h = 1.0 + 0.05 * goal_diff - 0.1 * late_factor
        momentum_a = 1.0 - 0.05 * goal_diff - 0.1 * late_factor

        # Preencher features
        X[idx, 0] = minute / match_minutes            # minute_norm
        X[idx, 1] = hs_partial                        # home_score_partial
        X[idx, 2] = as_partial                        # away_score_partial
        X[idx, 3] = goal_diff                         # goal_diff
        X[idx, 4] = remaining_frac                    # remaining_fraction
        X[idx, 5] = lambda_remaining_h                # home_lambda_remaining
        X[idx, 6] = lambda_remaining_a                # away_lambda_remaining
        X[idx, 7] = home_reds                         # home_red_cards
        X[idx, 8] = away_reds                         # away_red_cards
        X[idx, 9] = home_corners                      # home_corners
        X[idx, 10] = away_corners                     # away_corners
        X[idx, 11] = hawkes_h                         # hawkes_intensity_home
        X[idx, 12] = hawkes_a                         # hawkes_intensity_away
        X[idx, 13] = momentum_h                       # momentum_home_factor
        X[idx, 14] = momentum_a                       # momentum_away_factor

        # Target: probabilidade de gol no intervalo [t, t+Δ]
        # Heurística baseada nos gols restantes
        frac_window = min(window_minutes, match_minutes - minute) / max(
            match_minutes - minute, 1
        )
        expected_h = remaining_h * frac_window
        expected_a = remaining_a * frac_window

        # Decide target via probabilidade
        p_no_goal = np.exp(-(expected_h + expected_a))
        p_home = (1 - p_no_goal) * (expected_h / max(expected_h + expected_a, 0.01))
        p_away = (1 - p_no_goal) * (expected_a / max(expected_h + expected_a, 0.01))

        # Atribuir classe determinística (mais provável)
        probs = [p_no_goal, p_home, p_away]
        y[idx] = int(np.argmax(probs))

    return X, y


def _reconstruct_past_goals(
    home_partial: int, away_partial: int, current_minute: int
) -> list[HawkesGoalEvent]:
    """Reconstrói gols passados distribuídos uniformemente até o minuto atual."""
    events = []
    total = home_partial + away_partial
    if total == 0:
        return events

    # Distribuir uniformemente no intervalo [1, current_minute]
    step = max(current_minute / (total + 1), 1.0)
    teams = ["home"] * home_partial + ["away"] * away_partial

    for i, team in enumerate(teams):
        minute = step * (i + 1)
        events.append(HawkesGoalEvent(minute=min(minute, current_minute - 0.1), team=team))

    return events


def train_gbm_walkforward(
    min_season: int = 2010,
    val_season: int = 2022,
    max_season: int = 2026,
    window_minutes: int = 10,
    n_estimators: int = 300,
    seed: int = 42,
) -> tuple[InPlayGBMModel, GBMTrainResult]:
    """Treina GBM com walk-forward: treino em [min_season, val_season) e val em val_season.

    Args:
        min_season: início do treino.
        val_season: edição de validação.
        max_season: limite para construção de timeline.
        window_minutes: janela de predição.
        n_estimators: árvores no GBM.
        seed: seed de reprodutibilidade.

    Returns:
        Tupla (modelo treinado, resultado com métricas).
    """
    import structlog

    log = structlog.get_logger()
    log.info("gbm_train_started", min_season=min_season, val_season=val_season)

    # Construir timeline
    timeline = build_timeline_from_fixtures(min_season=min_season, max_season=max_season)
    if timeline.empty:
        log.warning("gbm_train_empty_timeline")
        model = InPlayGBMModel(window_minutes=window_minutes)
        return model, GBMTrainResult(
            train_logloss=0, val_logloss=0,
            train_accuracy=0, val_accuracy=0,
            n_train=0, n_val=0,
            feature_importance={},
        )

    # Split temporal
    train_df = timeline[timeline["season"] < val_season]
    val_df = timeline[timeline["season"] >= val_season]

    log.info("gbm_split", n_train=len(train_df), n_val=len(val_df))

    # Carregar params Hawkes
    hawkes_params = load_hawkes_params()

    # Construir datasets
    X_train, y_train = build_gbm_dataset(train_df, window_minutes, hawkes_params)
    X_val, y_val = build_gbm_dataset(val_df, window_minutes, hawkes_params)

    # Treinar
    model = InPlayGBMModel(window_minutes=window_minutes)
    metrics = model.fit(
        X_train, y_train,
        eval_X=X_val if len(X_val) > 0 else None,
        eval_y=y_val if len(y_val) > 0 else None,
        n_estimators=n_estimators,
        seed=seed,
    )

    # Importância
    importance = model.feature_importance()

    result = GBMTrainResult(
        train_logloss=metrics.get("train_logloss", 0),
        val_logloss=metrics.get("val_logloss", 0),
        train_accuracy=metrics.get("train_accuracy", 0),
        val_accuracy=metrics.get("val_accuracy", 0),
        n_train=len(X_train),
        n_val=len(X_val),
        feature_importance=importance,
    )

    log.info(
        "gbm_train_completed",
        train_logloss=round(result.train_logloss, 4),
        val_logloss=round(result.val_logloss, 4),
        val_accuracy=round(result.val_accuracy, 3),
        top_features=sorted(importance.items(), key=lambda x: -x[1])[:5],
    )

    # Salvar artefato
    path = model.save()
    log.info("gbm_model_saved", path=str(path))

    return model, result


def run_gbm_training(
    min_season: int = 2010,
    val_season: int = 2022,
    max_season: int = 2026,
    seed: int = 42,
) -> GBMTrainResult:
    """Entrypoint simplificado para treino do GBM."""
    _, result = train_gbm_walkforward(
        min_season=min_season,
        val_season=val_season,
        max_season=max_season,
        seed=seed,
    )
    return result
