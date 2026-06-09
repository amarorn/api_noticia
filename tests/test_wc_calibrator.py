"""Testes para models/wc_calibrator.py — calibração Platt scaling 3 classes."""
from __future__ import annotations

import numpy as np
import pytest

from models.wc_calibrator import WcCalibrator, CalibrationMetrics, compute_ece, LABELS


@pytest.fixture
def synthetic_data():
    """Gera dados sintéticos com probabilidades Dirichlet e rótulos amostrados."""
    rng = np.random.default_rng(123)
    n = 300
    probs = rng.dirichlet([3, 1.2, 1.5], size=n)
    labels_idx = [rng.choice(3, p=p) for p in probs]
    labels = np.array(LABELS)[labels_idx]
    return probs, labels


class TestWcCalibratorPlatt:
    """Testes do calibrador com método Platt (default)."""

    def test_fit_returns_metrics(self, synthetic_data):
        probs, labels = synthetic_data
        cal = WcCalibrator()
        metrics = cal.fit(probs, labels)
        assert isinstance(metrics, CalibrationMetrics)
        assert metrics.n_samples == 300
        assert metrics.method == "platt"

    def test_calibrate_sums_to_one(self, synthetic_data):
        probs, labels = synthetic_data
        cal = WcCalibrator()
        cal.fit(probs, labels)
        calibrated = cal.calibrate(probs)
        row_sums = calibrated.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)

    def test_calibrate_values_in_range(self, synthetic_data):
        probs, labels = synthetic_data
        cal = WcCalibrator()
        cal.fit(probs, labels)
        calibrated = cal.calibrate(probs)
        assert (calibrated >= 0).all()
        assert (calibrated <= 1).all()

    def test_calibrate_single_consistent(self, synthetic_data):
        probs, labels = synthetic_data
        cal = WcCalibrator()
        cal.fit(probs, labels)
        single = cal.calibrate_single(0.5, 0.3, 0.2)
        assert set(single.keys()) == {"1", "X", "2"}
        assert abs(sum(single.values()) - 1.0) < 1e-6

    def test_unfitted_returns_identity(self, synthetic_data):
        """Calibrador não ajustado retorna probabilidades originais (fallback)."""
        probs, _ = synthetic_data
        cal = WcCalibrator()
        result = cal.calibrate(probs)
        np.testing.assert_array_equal(result, probs)

    def test_brier_improves_or_stable(self, synthetic_data):
        """Brier não deve piorar drasticamente com calibração."""
        probs, labels = synthetic_data
        cal = WcCalibrator()
        metrics = cal.fit(probs, labels)
        # Aceita até +0.01 de piora (Platt com poucos dados pode não ajudar)
        assert metrics.brier_after <= metrics.brier_before + 0.01


class TestWcCalibratorIsotonic:
    """Testes do calibrador com método isotônico."""

    def test_isotonic_fit_and_calibrate(self, synthetic_data):
        probs, labels = synthetic_data
        cal = WcCalibrator(method="isotonic")
        metrics = cal.fit(probs, labels)
        assert metrics.method == "isotonic"
        calibrated = cal.calibrate(probs)
        row_sums = calibrated.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-6)


class TestECE:
    """Testes da função compute_ece."""

    def test_perfect_calibration_zero_ece(self):
        """Modelo perfeitamente calibrado tem ECE = 0."""
        # Todas previsões com confiança 1.0 e corretas
        probs = np.eye(3)[[0, 1, 2, 0, 1, 2]]
        labels = np.array(["1", "X", "2", "1", "X", "2"])
        ece = compute_ece(probs, labels)
        assert ece == pytest.approx(0.0, abs=1e-6)

    def test_ece_range(self, synthetic_data):
        probs, labels = synthetic_data
        ece = compute_ece(probs, labels)
        assert 0.0 <= ece <= 1.0

    def test_shape_validation(self):
        cal = WcCalibrator()
        with pytest.raises(ValueError, match="shape"):
            cal.fit(np.array([[0.5, 0.5]]), np.array(["1"]))
