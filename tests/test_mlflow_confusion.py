"""Testes de matriz de confusão holdout + MLflow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from pipelines.mlflow_tracking import apply_manifest_to_run, log_holdout_confusion_figure


def test_log_holdout_confusion_figure_writes_png():
    holdout_eval = {
        "validation_season": 2022,
        "n_samples": 4,
        "accuracy": 0.5,
        "labels": ["1", "X", "2"],
        "confusion_matrix": [
            [1, 0, 0],
            [0, 1, 0],
            [1, 0, 0],
        ],
    }

    with (
        patch("matplotlib.use"),
        patch("matplotlib.pyplot.subplots") as subplots,
        patch("matplotlib.pyplot.close"),
        patch("sklearn.metrics.ConfusionMatrixDisplay") as disp_cls,
        patch("mlflow.log_figure") as log_figure,
    ):
        fig = MagicMock()
        ax = MagicMock()
        subplots.return_value = (fig, ax)
        disp = MagicMock()
        disp_cls.return_value = disp

        log_holdout_confusion_figure(holdout_eval)

    disp.plot.assert_called_once()
    log_figure.assert_called_once_with(fig, "plots/confusion_matrix_ensemble.png")


def test_apply_manifest_logs_confusion_when_present():
    manifest = {
        "training_metrics": {"holdout_accuracy": 0.53},
        "collab_metrics": {"accuracy": 0.5, "brier_score": 0.19},
        "ensemble_weights": {"dixon_coles": 0.4, "logistic": 0.6},
        "holdout_eval": {
            "validation_season": 2022,
            "n_samples": 8,
            "accuracy": 0.5,
            "labels": ["1", "X", "2"],
            "confusion_matrix": [[1, 0, 0], [0, 1, 0], [1, 0, 0]],
        },
    }

    with (
        patch("mlflow.log_param"),
        patch("mlflow.log_metric"),
        patch("pipelines.mlflow_tracking.log_holdout_confusion_figure") as log_cm,
    ):
        apply_manifest_to_run(manifest, log_artifacts=True)

    log_cm.assert_called_once_with(manifest["holdout_eval"])
