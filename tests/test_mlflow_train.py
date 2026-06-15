from unittest.mock import MagicMock, patch

from pipelines.mlflow_tracking import log_wc_train_run


def test_log_wc_train_run_logs_metrics_and_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr("pipelines.mlflow_tracking.settings.wc_artifact_dir", tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    (tmp_path / "predictor.pkl").write_bytes(b"pickle")

    manifest = {
        "artifact_version": 6,
        "created_at": "2026-06-06T01:51:02.693201+00:00",
        "fixture_rows": 964,
        "fixtures_fingerprint": "fp-test",
        "hyperparams": {"elo_home_adv": 30.0},
        "training_metrics": {
            "train_size": 900,
            "holdout_season": 2022,
            "holdout_accuracy": 0.53125,
        },
        "collab_metrics": {
            "accuracy": 0.5,
            "brier_score": 0.1925,
            "log_loss": 0.967,
            "validation_size": 64,
        },
        "ensemble_weights": {"dixon_coles": 0.3, "logistic": 0.7},
        "holdout_eval": {
            "validation_season": 2022,
            "n_samples": 64,
            "accuracy": 0.5,
            "labels": ["1", "X", "2"],
            "confusion_matrix": [[10, 2, 1], [3, 4, 2], [1, 1, 5]],
        },
    }

    mock_run = MagicMock()
    mock_run.info.run_id = "run-abc"
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_run

    with (
        patch("mlflow.set_tracking_uri"),
        patch("mlflow.set_experiment"),
        patch("mlflow.start_run", return_value=mock_cm) as start_run,
        patch("pipelines.mlflow_tracking.apply_manifest_to_run") as apply_manifest,
        patch("pipelines.mlflow_tracking.log_holdout_confusion_figure") as log_cm,
    ):
        run_id = log_wc_train_run(manifest=manifest, elapsed_sec=810.5)

    assert run_id == "run-abc"
    start_run.assert_called_once()
    apply_manifest.assert_called_once_with(
        manifest,
        elapsed_sec=810.5,
        log_artifacts=True,
    )
    log_cm.assert_not_called()
