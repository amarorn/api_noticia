"""
Calibrador pós-hoc para probabilidades 3 classes (1/X/2) do ensemble WC.

Implementa Platt scaling (regressão logística) por classe com normalização
para garantir que as probabilidades somem 1. Mede ECE (Expected Calibration
Error) antes e depois da calibração.

Referência: Zadrozny & Elkan (2002), Platt (1999).
Spec: docs/specs/spec-fase-0-reorganizacao.md — Fase 0.1
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


LABELS = ("1", "X", "2")
"""Ordem canônica das classes: vitória mandante, empate, vitória visitante."""


@dataclass
class CalibrationMetrics:
    """Métricas de calibração pré e pós ajuste."""

    ece_before: float
    ece_after: float
    brier_before: float
    brier_after: float
    n_samples: int
    method: str = "platt"


@dataclass
class WcCalibrator:
    """Calibrador Platt scaling para 3 classes (1/X/2).

    Ajusta uma regressão logística (sigmoid) por classe sobre as
    probabilidades brutas do ensemble, mapeando p_raw → p_calibrada.
    Após calibrar cada classe independentemente, normaliza para somar 1.

    Uso:
        cal = WcCalibrator()
        metrics = cal.fit(probs_matrix, y_true)
        probs_cal = cal.calibrate(probs_matrix)
    """

    method: str = "platt"
    _fitted: bool = field(default=False, repr=False)
    _calibrators: dict[str, LogisticRegression | IsotonicRegression] = field(
        default_factory=dict, repr=False
    )
    _metrics: CalibrationMetrics | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def fit(
        self,
        probs: NDArray[np.floating],
        y_true: list[str] | NDArray,
        *,
        method: str | None = None,
    ) -> CalibrationMetrics:
        """Ajusta o calibrador sobre probabilidades do ensemble.

        Args:
            probs: Array (N, 3) com colunas [P(1), P(X), P(2)].
            y_true: Rótulos reais — valores em {"1", "X", "2"}.
            method: "platt" (default) ou "isotonic".

        Returns:
            CalibrationMetrics com ECE e Brier antes/depois.
        """
        if method is not None:
            self.method = method

        probs = np.asarray(probs, dtype=np.float64)
        y_true = np.asarray(y_true)
        n = len(y_true)

        if probs.shape != (n, 3):
            raise ValueError(
                f"probs deve ter shape (N, 3), recebeu {probs.shape}"
            )

        # Métricas antes da calibração
        ece_before = _compute_ece(probs, y_true)
        brier_before = _brier_multiclass(probs, y_true)

        # Ajustar um calibrador por classe (one-vs-all)
        self._calibrators = {}
        for i, label in enumerate(LABELS):
            y_bin = (y_true == label).astype(np.float64)
            p_class = probs[:, i].reshape(-1, 1)

            if self.method == "isotonic":
                cal = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
                cal.fit(p_class.ravel(), y_bin)
            else:
                # Platt scaling: logística simples sobre logit da probabilidade
                cal = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
                # Usar log-odds como feature para evitar boundary issues
                p_safe = np.clip(p_class, 1e-6, 1 - 1e-6)
                logit_p = np.log(p_safe / (1 - p_safe))
                cal.fit(logit_p, y_bin)

            self._calibrators[label] = cal

        self._fitted = True

        # Métricas depois da calibração
        probs_cal = self.calibrate(probs)
        ece_after = _compute_ece(probs_cal, y_true)
        brier_after = _brier_multiclass(probs_cal, y_true)

        self._metrics = CalibrationMetrics(
            ece_before=round(ece_before, 6),
            ece_after=round(ece_after, 6),
            brier_before=round(brier_before, 6),
            brier_after=round(brier_after, 6),
            n_samples=n,
            method=self.method,
        )
        return self._metrics

    def calibrate(self, probs: NDArray[np.floating]) -> NDArray[np.float64]:
        """Aplica calibração sobre array (N, 3) → (N, 3) normalizado.

        Se o calibrador não foi ajustado, retorna as probabilidades originais
        (identidade — fallback seguro).
        """
        probs = np.asarray(probs, dtype=np.float64)
        if not self._fitted:
            return probs

        n = probs.shape[0]
        cal_probs = np.zeros((n, 3), dtype=np.float64)

        for i, label in enumerate(LABELS):
            cal = self._calibrators[label]
            p_class = probs[:, i]

            if self.method == "isotonic":
                cal_probs[:, i] = cal.predict(p_class)
            else:
                p_safe = np.clip(p_class, 1e-6, 1 - 1e-6)
                logit_p = np.log(p_safe / (1 - p_safe)).reshape(-1, 1)
                cal_probs[:, i] = cal.predict_proba(logit_p)[:, 1]

        # Normalizar para somar 1 por linha
        row_sums = cal_probs.sum(axis=1, keepdims=True)
        row_sums = np.maximum(row_sums, 1e-9)
        cal_probs = cal_probs / row_sums

        return cal_probs

    def calibrate_single(self, prob_home: float, prob_draw: float, prob_away: float) -> dict[str, float]:
        """Calibra uma única previsão. Retorna dict {"1": ..., "X": ..., "2": ...}."""
        probs = np.array([[prob_home, prob_draw, prob_away]])
        cal = self.calibrate(probs)[0]
        return {"1": float(cal[0]), "X": float(cal[1]), "2": float(cal[2])}

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def metrics(self) -> CalibrationMetrics | None:
        return self._metrics


# ------------------------------------------------------------------
# Funções utilitárias de métricas
# ------------------------------------------------------------------


def _compute_ece(
    probs: NDArray[np.floating],
    y_true: NDArray,
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error (ECE) para classificação multiclasse.

    Agrupa previsões por confiança (max prob) em bins e mede a diferença
    média ponderada entre confiança e acurácia observada.
    """
    confidences = probs.max(axis=1)
    predictions = np.array([LABELS[i] for i in probs.argmax(axis=1)])
    accuracies = (predictions == y_true).astype(np.float64)

    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)

    for b in range(n_bins):
        lo, hi = bin_boundaries[b], bin_boundaries[b + 1]
        mask = (confidences > lo) & (confidences <= hi)
        if not mask.any():
            continue
        bin_size = mask.sum()
        avg_confidence = confidences[mask].mean()
        avg_accuracy = accuracies[mask].mean()
        ece += (bin_size / n) * abs(avg_accuracy - avg_confidence)

    return float(ece)


def _brier_multiclass(probs: NDArray[np.floating], y_true: NDArray) -> float:
    """Brier score multiclasse: média de (p_i - y_i)^2 sobre todas as classes."""
    n = len(y_true)
    if n == 0:
        return 0.0
    total = 0.0
    for i, label in enumerate(LABELS):
        targets = (y_true == label).astype(np.float64)
        total += ((probs[:, i] - targets) ** 2).sum()
    return float(total / (n * len(LABELS)))


def compute_ece(probs: NDArray[np.floating], y_true: NDArray, n_bins: int = 10) -> float:
    """API pública para computar ECE — usada em pipelines de avaliação."""
    return _compute_ece(np.asarray(probs), np.asarray(y_true), n_bins)
