"""LightGBM para predição de gol nos próximos N minutos (in-play).

Modelo binário: dado o estado do jogo no minuto t,
qual a probabilidade de haver pelo menos 1 gol em [t, t+Δ]?

Pode ser estendido para multiclasse:
- 0 = sem gol
- 1 = gol home
- 2 = gol away

Features de estado:
- minute (normalizado 0–1)
- home_score_partial, away_score_partial
- goal_diff
- remaining_fraction (do NHPP)
- home_lambda_remaining, away_lambda_remaining (do Poisson base)
- home_red_cards, away_red_cards
- home_corners, away_corners (proxy de pressão)
- hawkes_intensity_home, hawkes_intensity_away
- momentum_home_factor, momentum_away_factor

Target: {0, 1, 2} — quem marca primeiro no intervalo.

Spec: docs/specs/spec-fase-3-modelo-avancado.md § 5.2
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from config import settings

# Features usadas pelo GBM
GBM_FEATURES = [
    "minute_norm",              # minute / 90
    "home_score_partial",
    "away_score_partial",
    "goal_diff",                # home - away
    "remaining_fraction",       # fração NHPP restante
    "home_lambda_remaining",    # λ restante (Poisson) por minuto
    "away_lambda_remaining",
    "home_red_cards",
    "away_red_cards",
    "home_corners",
    "away_corners",
    "hawkes_intensity_home",    # intensidade Hawkes instantânea
    "hawkes_intensity_away",
    "momentum_home_factor",     # fator do momentum calibrado
    "momentum_away_factor",
]

# Classes do modelo multiclasse
GBM_CLASSES = {0: "no_goal", 1: "goal_home", 2: "goal_away"}


@dataclass
class GBMInPlayPrediction:
    """Predição do modelo GBM para o próximo intervalo."""

    prob_no_goal: float
    prob_goal_home: float
    prob_goal_away: float
    prob_any_goal: float
    window_minutes: int = 10

    @property
    def probs_1x2(self) -> dict[str, float]:
        """Probabilidade de quem marca primeiro no intervalo."""
        return {
            "home": self.prob_goal_home,
            "away": self.prob_goal_away,
            "none": self.prob_no_goal,
        }


class InPlayGBMModel:
    """Wrapper do LightGBM para predição in-play de gols.

    Suporta treinamento, predição e persistência do modelo.
    Usa import lazy do LightGBM para não quebrar em ambientes sem a lib.
    """

    def __init__(self, window_minutes: int = 10):
        """Inicializa o modelo.

        Args:
            window_minutes: janela de predição em minutos (default 10).
        """
        self.window_minutes = window_minutes
        self._model = None
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def fit(
        self,
        X: NDArray[np.float64],
        y: NDArray[np.int64],
        eval_X: NDArray[np.float64] | None = None,
        eval_y: NDArray[np.int64] | None = None,
        n_estimators: int = 300,
        learning_rate: float = 0.05,
        max_depth: int = 6,
        min_child_samples: int = 50,
        reg_lambda: float = 1.0,
        seed: int = 42,
    ) -> dict[str, float]:
        """Treina o modelo multiclasse.

        Args:
            X: features (n_samples, n_features).
            y: target multiclasse {0, 1, 2}.
            eval_X: dados de validação (opcional).
            eval_y: targets de validação (opcional).
            n_estimators: número de árvores.
            learning_rate: taxa de aprendizado.
            max_depth: profundidade máxima.
            min_child_samples: mínimo de amostras por folha.
            reg_lambda: regularização L2.
            seed: seed de reprodutibilidade.

        Returns:
            Dict com métricas de treino.
        """
        import lightgbm as lgb

        params = {
            "objective": "multiclass",
            "num_class": 3,
            "metric": "multi_logloss",
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "min_child_samples": min_child_samples,
            "reg_lambda": reg_lambda,
            "random_state": seed,
            "verbose": -1,
            "n_jobs": -1,
        }

        self._model = lgb.LGBMClassifier(**params)

        callbacks = []
        eval_set = None
        if eval_X is not None and eval_y is not None:
            eval_set = [(eval_X, eval_y)]

        self._model.fit(
            X, y,
            eval_set=eval_set,
            callbacks=callbacks,
        )
        self._fitted = True

        # Métricas básicas no treino
        from sklearn.metrics import log_loss, accuracy_score

        y_pred = self._model.predict_proba(X)
        metrics = {
            "train_logloss": float(log_loss(y, y_pred)),
            "train_accuracy": float(accuracy_score(y, y_pred.argmax(axis=1))),
        }

        if eval_X is not None and eval_y is not None:
            y_eval_pred = self._model.predict_proba(eval_X)
            metrics["val_logloss"] = float(log_loss(eval_y, y_eval_pred))
            metrics["val_accuracy"] = float(accuracy_score(
                eval_y, y_eval_pred.argmax(axis=1)
            ))

        return metrics

    def predict(self, X: NDArray[np.float64]) -> list[GBMInPlayPrediction]:
        """Prediz probabilidades para cada amostra.

        Args:
            X: features (n_samples, n_features).

        Returns:
            Lista de GBMInPlayPrediction.
        """
        if not self._fitted or self._model is None:
            raise RuntimeError("Modelo GBM não treinado. Chame fit() primeiro.")

        probs = self._model.predict_proba(X)
        results = []
        for row in probs:
            results.append(GBMInPlayPrediction(
                prob_no_goal=float(row[0]),
                prob_goal_home=float(row[1]),
                prob_goal_away=float(row[2]),
                prob_any_goal=float(row[1] + row[2]),
                window_minutes=self.window_minutes,
            ))
        return results

    def predict_single(self, features: dict[str, float]) -> GBMInPlayPrediction:
        """Prediz para um único estado de jogo.

        Args:
            features: dict com keys de GBM_FEATURES.

        Returns:
            GBMInPlayPrediction.
        """
        X = np.array([[features.get(f, 0.0) for f in GBM_FEATURES]])
        return self.predict(X)[0]

    def feature_importance(self) -> dict[str, float]:
        """Importância das features (gain)."""
        if not self._fitted or self._model is None:
            return {}

        importance = self._model.feature_importances_
        return {
            feat: float(imp)
            for feat, imp in zip(GBM_FEATURES, importance)
        }

    def save(self, path: Path | None = None) -> Path:
        """Persiste modelo treinado em pickle."""
        if path is None:
            path = settings.lake_root / "artifacts" / "inplay_gbm.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump({
                "model": self._model,
                "window_minutes": self.window_minutes,
                "features": GBM_FEATURES,
                "fitted": self._fitted,
            }, f)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "InPlayGBMModel":
        """Carrega modelo treinado; retorna instância não-treinada se não existe."""
        if path is None:
            path = settings.lake_root / "artifacts" / "inplay_gbm.pkl"

        if not path.exists():
            return cls()

        try:
            with open(path, "rb") as f:
                data = pickle.load(f)

            instance = cls(window_minutes=data.get("window_minutes", 10))
            instance._model = data["model"]
            instance._fitted = data.get("fitted", True)
            return instance
        except (pickle.UnpicklingError, KeyError, EOFError):
            return cls()
