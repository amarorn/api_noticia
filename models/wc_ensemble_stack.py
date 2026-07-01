"""Meta-learner de stacking para o ensemble in-play.

Substitui pesos manuais de bucket temporal por LogisticRegression
treinada para minimizar LogLoss nas partidas históricas.

Meta-features:
  - Probabilidades de cada componente (Poisson, Hawkes, GBM, Market) × {1, X, 2}
  - Contexto: minute_norm, score_diff, remaining_frac

Target: y_final ∈ {"1", "X", "2"} do resultado real da partida.

Caso o artefato não exista, blend_ensemble() usa pesos manuais como fallback
(comportamento pré-existente inalterado).
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from config import settings

_STACK_PATH = settings.lake_root / "artifacts" / "ensemble_stack.pkl"

_META_FEATURES = [
    "p_poisson_1", "p_poisson_x", "p_poisson_2",
    "p_hawkes_1",  "p_hawkes_x",  "p_hawkes_2",
    "p_gbm_1",     "p_gbm_x",     "p_gbm_2",
    "p_market_1",  "p_market_x",  "p_market_2",
    "minute_norm",
    "score_diff",
    "remaining_frac",
]

_LABEL_MAP = {"1": 0, "X": 1, "2": 2}
_LABEL_INV = {0: "1", 1: "X", 2: "2"}


class StackedEnsemble:
    """LogisticRegression multinomial sobre meta-features do ensemble in-play.

    Uso:
        stack = StackedEnsemble.load()
        if stack.is_fitted:
            probs = stack.predict(meta_features_dict)
        else:
            # fallback para pesos manuais em blend_ensemble()
    """

    def __init__(self) -> None:
        self._model = None
        self._fitted = False

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    def _to_frame(self, features: dict[str, float]) -> pd.DataFrame:
        row = {f: float(features.get(f, 0.0)) for f in _META_FEATURES}
        return pd.DataFrame([row], columns=_META_FEATURES)

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series | list[str],
        C: float = 1.0,
        seed: int = 42,
    ) -> dict[str, float]:
        """Treina o meta-learner.

        Args:
            X: DataFrame com colunas em _META_FEATURES.
            y: labels {"1", "X", "2"} ou {0, 1, 2}.
            C: regularização inversa (LogisticRegression).
            seed: reprodutibilidade.

        Returns:
            Métricas: train_logloss, train_accuracy, n_samples.
        """
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import log_loss

        X_arr = X.reindex(columns=_META_FEATURES, fill_value=0.0).values.astype(np.float64)
        y_arr = np.array([
            _LABEL_MAP[str(lbl)] if str(lbl) in _LABEL_MAP else int(lbl)
            for lbl in y
        ])

        self._model = LogisticRegression(
            multi_class="multinomial",
            solver="lbfgs",
            C=C,
            max_iter=1000,
            random_state=seed,
        )
        self._model.fit(X_arr, y_arr)
        self._fitted = True

        proba = self._model.predict_proba(X_arr)
        return {
            "train_logloss": float(log_loss(y_arr, proba)),
            "train_accuracy": float((self._model.predict(X_arr) == y_arr).mean()),
            "n_samples": int(len(y_arr)),
        }

    def predict(self, features: dict[str, float]) -> dict[str, float]:
        """Prediz probabilidades 1X2 finais.

        Returns:
            {"1": p, "X": p, "2": p} normalizado.
        """
        if not self._fitted or self._model is None:
            raise RuntimeError("StackedEnsemble não treinado.")

        X = self._to_frame(features).values
        proba = self._model.predict_proba(X)[0]
        result = {
            _LABEL_INV.get(int(cls), str(cls)): float(p)
            for cls, p in zip(self._model.classes_, proba)
        }
        for k in ("1", "X", "2"):
            result.setdefault(k, 0.0)
        total = sum(result.values())
        return {k: v / total for k, v in result.items()} if total > 0 else result

    def save(self, path: Path | None = None) -> Path:
        path = path or _STACK_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"model": self._model, "fitted": self._fitted}, f)
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "StackedEnsemble":
        path = path or _STACK_PATH
        inst = cls()
        if not path.exists():
            return inst
        try:
            with open(path, "rb") as f:
                data = pickle.load(f)
            inst._model = data["model"]
            inst._fitted = data.get("fitted", True)
        except Exception:
            pass
        return inst


# ---------------------------------------------------------------------------
# Singleton lazy
# ---------------------------------------------------------------------------

_LOADED_STACK: StackedEnsemble | None = None
_STACK_CHECKED = False


def get_stack() -> StackedEnsemble | None:
    """Retorna meta-learner treinado ou None se indisponível."""
    global _LOADED_STACK, _STACK_CHECKED
    if not _STACK_CHECKED:
        s = StackedEnsemble.load()
        _LOADED_STACK = s if s.is_fitted else None
        _STACK_CHECKED = True
    return _LOADED_STACK


def invalidate_stack_cache() -> None:
    """Recarrega o stack na próxima chamada a get_stack()."""
    global _LOADED_STACK, _STACK_CHECKED
    _LOADED_STACK = None
    _STACK_CHECKED = False


# ---------------------------------------------------------------------------
# Meta-features builder (chamado por blend_ensemble)
# ---------------------------------------------------------------------------

def build_meta_features(
    poisson_probs: dict[str, float] | None,
    hawkes_probs: dict[str, float] | None,
    gbm_probs: dict[str, float] | None,
    market_probs: dict[str, float] | None,
    minute: float,
    score_diff: float = 0.0,
    remaining_frac: float = 0.5,
) -> dict[str, float]:
    """Monta dict de meta-features para o StackedEnsemble."""

    def _p(d: dict[str, float] | None, k: str) -> float:
        return float(d.get(k, 1 / 3)) if d else 1 / 3

    return {
        "p_poisson_1": _p(poisson_probs, "1"),
        "p_poisson_x": _p(poisson_probs, "X"),
        "p_poisson_2": _p(poisson_probs, "2"),
        "p_hawkes_1":  _p(hawkes_probs, "1"),
        "p_hawkes_x":  _p(hawkes_probs, "X"),
        "p_hawkes_2":  _p(hawkes_probs, "2"),
        "p_gbm_1":     _p(gbm_probs, "1"),
        "p_gbm_x":     _p(gbm_probs, "X"),
        "p_gbm_2":     _p(gbm_probs, "2"),
        "p_market_1":  _p(market_probs, "1"),
        "p_market_x":  _p(market_probs, "X"),
        "p_market_2":  _p(market_probs, "2"),
        "minute_norm":    float(minute) / 90.0,
        "score_diff":     float(score_diff),
        "remaining_frac": float(remaining_frac),
    }
