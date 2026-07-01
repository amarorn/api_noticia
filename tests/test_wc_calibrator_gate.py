"""Gate de qualidade do calibrador Platt (holdout pequeno)."""
from __future__ import annotations

from models.wc_calibrator import (
    CalibrationMetrics,
    WcCalibrator,
    apply_calibrator_if_passing,
    calibrator_passes_quality_gate,
)


def test_gate_rejects_when_ece_worsens():
    metrics = CalibrationMetrics(
        ece_before=0.06,
        ece_after=0.085,
        brier_before=0.20,
        brier_after=0.199,
        n_samples=64,
    )
    assert calibrator_passes_quality_gate(metrics) is False


def test_gate_accepts_when_ece_improves():
    metrics = CalibrationMetrics(
        ece_before=0.10,
        ece_after=0.07,
        brier_before=0.21,
        brier_after=0.20,
        n_samples=64,
    )
    assert calibrator_passes_quality_gate(metrics) is True


def test_apply_returns_identity_when_rejected():
    fitted = WcCalibrator()
    fitted._fitted = True
    metrics = CalibrationMetrics(
        ece_before=0.06,
        ece_after=0.08,
        brier_before=0.20,
        brier_after=0.19,
        n_samples=64,
    )
    out = apply_calibrator_if_passing(fitted, metrics, gate_enabled=True)
    assert out.is_fitted is False


def test_apply_keeps_calibrator_when_gate_disabled():
    fitted = WcCalibrator()
    fitted._fitted = True
    metrics = CalibrationMetrics(
        ece_before=0.06,
        ece_after=0.08,
        brier_before=0.20,
        brier_after=0.19,
        n_samples=64,
    )
    out = apply_calibrator_if_passing(fitted, metrics, gate_enabled=False)
    assert out is fitted
