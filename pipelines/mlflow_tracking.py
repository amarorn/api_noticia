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
