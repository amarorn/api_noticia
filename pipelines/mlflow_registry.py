"""Registro MLflow: backfill local e leaderboard sem retreino completo."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings
from models.wc_model_selection import (
    build_implementable_leaderboard,
    load_model_selection,
    pick_best_implementable_model,
    save_model_selection,
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def log_benchmark_snapshot(
    *,
    wc_report: dict[str, Any] | None = None,
    latest_snapshot: dict[str, Any] | None = None,
    run_name: str | None = None,
) -> str | None:
    """Registra snapshot consolidado no MLflow (experimento wc-benchmark)."""
    try:
        import mlflow
    except ImportError:
        return None

    from pipelines.mlflow_tracking import log_classification_benchmark, setup_mlflow

    wc_report = wc_report or _read_json(settings.lake_root / "reports" / "wc_benchmark_report.json")
    if not wc_report or not wc_report.get("metrics"):
        return None

    log_classification_benchmark(
        experiment_name=settings.mlflow_experiment_wc,
        run_name=run_name or f"benchmark-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        eval_season=int(wc_report.get("eval_season") or settings.wc_validation_season),
        train_samples=int(wc_report.get("train_samples") or 0),
        eval_samples=int(wc_report.get("eval_samples") or 0),
        metrics=wc_report["metrics"],
    )

    setup_mlflow(settings.mlflow_experiment_wc)
    leaderboard = build_implementable_leaderboard()
    best = pick_best_implementable_model(leaderboard)
    with mlflow.start_run(run_name=run_name or f"selection-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}") as run:
        mlflow.set_tag("run_kind", "model_selection")
        mlflow.log_param("selection_metric", settings.wc_model_selection_metric)
        mlflow.log_param("selected_model", best.get("model"))
        if best.get("metric_value") is not None:
            mlflow.log_metric(f"selected_{settings.wc_model_selection_metric}", float(best["metric_value"]))
        if best.get("accuracy") is not None:
            mlflow.log_metric("selected_accuracy", float(best["accuracy"]))
        if best.get("brier") is not None:
            mlflow.log_metric("selected_brier", float(best["brier"]))
        for row in leaderboard:
            prefix = row["model"]
            if row.get("accuracy") is not None:
                mlflow.log_metric(f"{prefix}_accuracy", float(row["accuracy"]))
            if row.get("brier") is not None:
                mlflow.log_metric(f"{prefix}_brier", float(row["brier"]))
        if latest_snapshot:
            snap_path = settings.lake_root / "reports" / "_mlflow_snapshot_upload.json"
            snap_path.write_text(json.dumps(latest_snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(snap_path))
            snap_path.unlink(missing_ok=True)
        return run.info.run_id
    return None


def backfill_mlflow_from_local(*, skip_artifacts: bool = False) -> dict[str, Any]:
    """Importa manifest e relatórios locais para o MLflow (sem treinar)."""
    result: dict[str, Any] = {
        "wc_train_run_id": None,
        "benchmark_run_id": None,
        "selection_saved": False,
        "errors": [],
    }

    manifest = _read_json(settings.wc_artifact_dir / "manifest.json")
    if manifest:
        try:
            from pipelines.mlflow_tracking import log_wc_train_run

            result["wc_train_run_id"] = log_wc_train_run(
                manifest=manifest,
                run_name=f"backfill-{manifest.get('created_at', 'wc')[:19]}",
                log_artifacts=not skip_artifacts,
            )
        except Exception as exc:
            result["errors"].append(f"wc_train: {exc}")
    else:
        result["errors"].append("manifest ausente em wc_predictor")

    wc_report = _read_json(settings.lake_root / "reports" / "wc_benchmark_report.json")
    latest = _read_json(settings.lake_root / "reports" / "model_benchmark_latest.json")

    try:
        result["benchmark_run_id"] = log_benchmark_snapshot(
            wc_report=wc_report,
            latest_snapshot=latest,
            run_name="backfill-benchmark",
        )
    except Exception as exc:
        result["errors"].append(f"benchmark: {exc}")

    if wc_report:
        save_model_selection(source="benchmark")
        result["selection_saved"] = True
        result["selection"] = pick_best_implementable_model()
    else:
        result["errors"].append("wc_benchmark_report.json ausente — rode run-model-benchmark")

    return result


def get_mlflow_leaderboard(*, limit: int = 20) -> list[dict[str, Any]]:
    """Lê runs de seleção/benchmark do MLflow; fallback para arquivo local."""
    try:
        import mlflow
        from mlflow.entities import ViewType
    except ImportError:
        return []

    from pipelines.mlflow_tracking import setup_mlflow

    setup_mlflow(settings.mlflow_experiment_wc)
    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name(settings.mlflow_experiment_wc)
    if experiment is None:
        return []

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string="tags.run_kind = 'model_selection'",
        order_by=["attributes.start_time DESC"],
        max_results=limit,
        run_view_type=ViewType.ACTIVE_ONLY,
    )
    rows: list[dict[str, Any]] = []
    for run in runs:
        raw_metrics = run.data.metrics
        if isinstance(raw_metrics, dict):
            metrics = {k: float(v) for k, v in raw_metrics.items()}
            raw_params = run.data.params
            params = raw_params if isinstance(raw_params, dict) else {p.key: p.value for p in raw_params}
        else:
            metrics = {m.key: m.value for m in raw_metrics}
            params = {p.key: p.value for p in run.data.params}
        rows.append(
            {
                "run_id": run.info.run_id,
                "run_name": run.info.run_name,
                "start_time": run.info.start_time,
                "selected_model": params.get("selected_model"),
                "selection_metric": params.get("selection_metric"),
                "selected_brier": metrics.get("selected_brier"),
                "selected_accuracy": metrics.get("selected_accuracy"),
            }
        )
    return rows


def model_registry_summary() -> dict[str, Any]:
    """Resumo para API: leaderboard local + seleção ativa + histórico MLflow."""
    active = load_model_selection()
    if active is None:
        active = save_model_selection(source="registry")

    return {
        "selection_mode": settings.wc_model_selection_mode,
        "selection_metric": settings.wc_model_selection_metric,
        "active_selection": active,
        "leaderboard": build_implementable_leaderboard(),
        "mlflow_runs": get_mlflow_leaderboard(limit=10),
        "mlflow_ui": "http://127.0.0.1:5001",
        "mlflow_tracking_uri": settings.mlflow_tracking_uri,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill MLflow a partir de manifest/relatórios locais (sem retreino)"
    )
    parser.add_argument(
        "--skip-artifacts",
        action="store_true",
        help="Não envia predictor.pkl ao MLflow (só métricas)",
    )
    args = parser.parse_args()

    result = backfill_mlflow_from_local(skip_artifacts=args.skip_artifacts)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("selection"):
        sel = result["selection"]
        print(
            f"\nModelo ativo: {sel.get('label')} ({sel.get('model')}) "
            f"| {sel.get('metric')}={sel.get('metric_value')}"
        )
    if result["errors"]:
        print("\nAvisos:", "; ".join(result["errors"]))


if __name__ == "__main__":
    main()
