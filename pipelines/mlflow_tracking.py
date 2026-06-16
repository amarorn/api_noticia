from __future__ import annotations

from pathlib import Path

from config import settings


def setup_mlflow(experiment_name: str) -> None:
    import mlflow

    uri = settings.mlflow_tracking_uri
    if uri.startswith("sqlite:///./"):
        db_path = Path(uri.removeprefix("sqlite:///./")).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment_name)


def log_classification_benchmark(
    *,
    experiment_name: str,
    run_name: str,
    eval_season: int,
    train_samples: int,
    eval_samples: int,
    metrics: list[dict],
    extra_params: dict[str, float | int | str] | None = None,
) -> None:
    import mlflow

    setup_mlflow(experiment_name)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_param("eval_season", eval_season)
        mlflow.log_param("train_samples", train_samples)
        mlflow.log_param("eval_samples", eval_samples)
        if extra_params:
            for key, value in extra_params.items():
                mlflow.log_param(key, value)
        for m in metrics:
            prefix = m["model"]
            mlflow.log_metric(f"{prefix}_accuracy", m["accuracy"])
            mlflow.log_metric(f"{prefix}_brier", m["brier"])
            mlflow.log_metric(f"{prefix}_log_loss", m["log_loss"])
            if "weights" in m:
                for key, value in m["weights"].items():
                    mlflow.log_param(f"{prefix}_blend_weight_{key}", value)


def log_wc_train_run(
    *,
    manifest: dict,
    elapsed_sec: float | None = None,
    run_name: str | None = None,
    log_artifacts: bool = True,
) -> str:
    import mlflow

    setup_mlflow(settings.mlflow_experiment_wc_train)

    created_at = manifest.get("created_at", "")
    if run_name is None:
        run_name = created_at[:19].replace(":", "-") if created_at else "wc-train"

    with mlflow.start_run(run_name=run_name) as run:
        apply_manifest_to_run(
            manifest,
            elapsed_sec=elapsed_sec,
            log_artifacts=log_artifacts,
        )
        return run.info.run_id


def apply_manifest_to_run(
    manifest: dict,
    *,
    elapsed_sec: float | None = None,
    log_artifacts: bool = True,
) -> None:
    """Grava params/métricas/artefatos do manifest no run MLflow ativo."""
    import mlflow

    training = manifest.get("training_metrics") or {}
    collab = manifest.get("collab_metrics") or {}
    ensemble = manifest.get("ensemble_weights") or {}
    hyperparams = manifest.get("hyperparams") or {}

    mlflow.log_param("artifact_version", manifest.get("artifact_version"))
    mlflow.log_param("fixture_rows", manifest.get("fixture_rows"))
    mlflow.log_param("train_size", training.get("train_size"))
    mlflow.log_param("holdout_season", training.get("holdout_season"))
    mlflow.log_param("feature_count", manifest.get("feature_count"))
    mlflow.log_param("logistic_calibration", manifest.get("logistic_calibration"))

    for key in (
        "fixtures_fingerprint",
        "squads_fingerprint",
        "hyperparams_fingerprint",
        "fifa_fingerprint",
        "odds_fingerprint",
        "baselines_fingerprint",
        "silver_fingerprint",
    ):
        if manifest.get(key):
            mlflow.log_param(key, manifest[key])

    for key, value in hyperparams.items():
        mlflow.log_param(f"hp_{key}", value)

    if training.get("holdout_accuracy") is not None:
        mlflow.log_metric("holdout_accuracy", float(training["holdout_accuracy"]))
    if collab.get("accuracy") is not None:
        mlflow.log_metric("ensemble_accuracy", float(collab["accuracy"]))
    if collab.get("brier_score") is not None:
        mlflow.log_metric("ensemble_brier", float(collab["brier_score"]))
    if collab.get("log_loss") is not None:
        mlflow.log_metric("ensemble_log_loss", float(collab["log_loss"]))
    if collab.get("validation_size") is not None:
        mlflow.log_metric("validation_size", float(collab["validation_size"]))
    if ensemble.get("dixon_coles") is not None:
        mlflow.log_metric("weight_dixon_coles", float(ensemble["dixon_coles"]))
    if ensemble.get("logistic") is not None:
        mlflow.log_metric("weight_logistic", float(ensemble["logistic"]))
    if elapsed_sec is not None:
        mlflow.log_metric("train_elapsed_sec", float(elapsed_sec))

    holdout_eval = manifest.get("holdout_eval")
    if log_artifacts and holdout_eval:
        log_holdout_confusion_figure(holdout_eval)

    manifest_path = settings.wc_artifact_dir / "manifest.json"
    if log_artifacts and manifest_path.exists():
        mlflow.log_artifact(str(manifest_path))

    predictor_path = settings.wc_artifact_dir / "predictor.pkl"
    if log_artifacts and predictor_path.exists():
        mlflow.log_artifact(str(predictor_path))


def log_holdout_confusion_figure(holdout_eval: dict) -> None:
    """Grava matriz de confusão do holdout na aba Artifacts do MLflow."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import mlflow
        import numpy as np
        from sklearn.metrics import ConfusionMatrixDisplay
    except ImportError:
        return

    matrix = holdout_eval.get("confusion_matrix")
    if not matrix:
        return

    labels = holdout_eval.get("labels") or ["1", "X", "2"]
    season = holdout_eval.get("validation_season", "")
    accuracy = holdout_eval.get("accuracy")
    n_samples = holdout_eval.get("n_samples")

    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    disp = ConfusionMatrixDisplay(
        confusion_matrix=np.array(matrix, dtype=int),
        display_labels=labels,
    )
    disp.plot(ax=ax, colorbar=False, cmap="Blues")
    title = f"Holdout {season}"
    if accuracy is not None:
        title += f" — acurácia {float(accuracy):.1%}"
    if n_samples is not None:
        title += f" (n={n_samples})"
    ax.set_title(title)
    fig.tight_layout()
    mlflow.log_figure(fig, "plots/confusion_matrix_ensemble.png")
    plt.close(fig)
