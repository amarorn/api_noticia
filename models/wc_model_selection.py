"""Seleção do melhor modelo WC implementável em produção (sem retreino)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from config import settings

SelectionMetric = Literal["brier", "accuracy"]
SelectionMode = Literal["ensemble", "auto"]
SelectionSource = Literal["benchmark", "mlflow", "registry"]

# Modelos que o WcPredictor consegue aplicar em runtime (sem GBM do benchmark offline).
IMPLEMENTABLE_MODELS = frozenset({"poisson", "logistic", "artifact_ensemble"})


def _selection_path() -> Path:
    return settings.lake_root / "artifacts" / "model_selection.json"

_MODEL_LABELS = {
    "poisson": "Poisson / Dixon-Coles",
    "logistic": "Regressão logística",
    "artifact_ensemble": "Ensemble treinado (collaborative)",
}


def _round4(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _load_manifest() -> dict[str, Any]:
    path = settings.wc_artifact_dir / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_wc_benchmark_report() -> dict[str, Any]:
    path = settings.lake_root / "reports" / "wc_benchmark_report.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_ensemble_metric(manifest: dict[str, Any]) -> dict[str, Any]:
    collab = manifest.get("collab_metrics") or {}
    train = manifest.get("training_metrics") or {}
    ensemble = manifest.get("ensemble_weights") or {}
    return {
        "model": "artifact_ensemble",
        "label": _MODEL_LABELS["artifact_ensemble"],
        "accuracy": _round4(collab.get("accuracy") or train.get("holdout_accuracy")),
        "brier": _round4(collab.get("brier_score")),
        "log_loss": _round4(collab.get("log_loss")),
        "weights": {
            "dixon_coles": ensemble.get("dixon_coles"),
            "logistic": ensemble.get("logistic"),
        },
        "implementable": True,
        "source": "artifact",
    }


def _normalize_benchmark_metric(row: dict[str, Any]) -> dict[str, Any] | None:
    name = str(row.get("model", ""))
    if name == "poisson":
        key = "poisson"
    elif name == "logistic":
        key = "logistic"
    else:
        return None
    return {
        "model": key,
        "label": _MODEL_LABELS[key],
        "accuracy": _round4(row.get("accuracy")),
        "brier": _round4(row.get("brier")),
        "log_loss": _round4(row.get("log_loss")),
        "weights": row.get("weights"),
        "implementable": True,
        "source": "benchmark",
    }


def build_implementable_leaderboard(
    *,
    manifest: dict[str, Any] | None = None,
    wc_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Ranking só com modelos usáveis pelo predictor em produção."""
    manifest = manifest if manifest is not None else _load_manifest()
    wc_report = wc_report if wc_report is not None else _load_wc_benchmark_report()

    rows: list[dict[str, Any]] = []
    if manifest:
        rows.append(_artifact_ensemble_metric(manifest))

    for metric in wc_report.get("metrics") or []:
        normalized = _normalize_benchmark_metric(metric)
        if normalized:
            rows.append(normalized)

    metric = settings.wc_model_selection_metric
    reverse = metric == "accuracy"

    def sort_key(item: dict[str, Any]) -> float:
        value = item.get(metric)
        if value is None:
            return float("inf") if not reverse else float("-inf")
        return float(value)

    rows.sort(key=sort_key, reverse=reverse)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def pick_best_implementable_model(
    leaderboard: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    board = leaderboard if leaderboard is not None else build_implementable_leaderboard()
    if not board:
        return {
            "model": "artifact_ensemble",
            "label": _MODEL_LABELS["artifact_ensemble"],
            "metric": settings.wc_model_selection_metric,
            "metric_value": None,
            "blend_weights": None,
            "reason": "sem_benchmark_usar_ensemble_artifact",
        }

    best = board[0]
    blend = _blend_for_model(best["model"], best.get("weights"), _load_manifest())
    return {
        "model": best["model"],
        "label": best.get("label") or best["model"],
        "metric": settings.wc_model_selection_metric,
        "metric_value": best.get(settings.wc_model_selection_metric),
        "accuracy": best.get("accuracy"),
        "brier": best.get("brier"),
        "blend_weights": blend,
        "reason": "melhor_modelo_implementavel",
        "rank": best.get("rank", 1),
    }


def _blend_for_model(
    model: str,
    weights: dict[str, Any] | None,
    manifest: dict[str, Any],
) -> dict[str, float]:
    if model == "poisson":
        return {"dixon_coles": 1.0, "logistic": 0.0}
    if model == "logistic":
        return {"dixon_coles": 0.0, "logistic": 1.0}
    ensemble = (manifest.get("ensemble_weights") or {}) if manifest else {}
    dc = float(ensemble.get("dixon_coles", 0.5))
    lg = float(ensemble.get("logistic", 0.5))
    total = dc + lg
    if total <= 0:
        return {"dixon_coles": 0.5, "logistic": 0.5}
    return {"dixon_coles": dc / total, "logistic": lg / total}


def resolve_blend_weights(
    default_dc: float,
    default_lg: float,
) -> tuple[float, float, dict[str, Any]]:
    """Retorna pesos Dixon-Coles/logística conforme modo de seleção."""
    mode = settings.wc_model_selection_mode
    meta: dict[str, Any] = {"mode": mode}

    if mode != "auto":
        meta["selected_model"] = "artifact_ensemble"
        meta["blend_weights"] = {"dixon_coles": default_dc, "logistic": default_lg}
        return default_dc, default_lg, meta

    selection = load_model_selection()
    if selection and selection.get("blend_weights"):
        blend = selection["blend_weights"]
        dc = float(blend.get("dixon_coles", default_dc))
        lg = float(blend.get("logistic", default_lg))
        meta.update(selection)
        return dc, lg, meta

    picked = pick_best_implementable_model()
    blend = picked.get("blend_weights") or {"dixon_coles": default_dc, "logistic": default_lg}
    dc = float(blend["dixon_coles"])
    lg = float(blend["logistic"])
    meta.update(picked)
    return dc, lg, meta


def save_model_selection(
    *,
    leaderboard: list[dict[str, Any]] | None = None,
    source: str = "benchmark",
) -> dict[str, Any]:
    board = leaderboard if leaderboard is not None else build_implementable_leaderboard()
    best = pick_best_implementable_model(board)
    payload = {
        "updated_at": datetime.now(UTC).isoformat(),
        "selection_mode": settings.wc_model_selection_mode,
        "selection_metric": settings.wc_model_selection_metric,
        "selection_source": source,
        "selected_model": best["model"],
        "selected_label": best.get("label"),
        "metric_value": best.get("metric_value"),
        "accuracy": best.get("accuracy"),
        "brier": best.get("brier"),
        "blend_weights": best.get("blend_weights"),
        "leaderboard": board,
    }
    path = _selection_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def load_model_selection() -> dict[str, Any] | None:
    path = _selection_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
