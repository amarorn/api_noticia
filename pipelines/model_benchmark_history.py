"""Benchmark consolidado dos modelos + histórico de evolução.

Executa métricas de pré-jogo WC, in-play e artefato em produção;
persiste snapshots em ``data/lake/reports/model_benchmark_history.json``.

CLI: run-model-benchmark [--skip-walkforward] [--seed-only]
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import settings

HISTORY_PATH = settings.lake_root / "reports" / "model_benchmark_history.json"
LATEST_PATH = settings.lake_root / "reports" / "model_benchmark_latest.json"


def _round4(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _load_manifest() -> dict[str, Any]:
    path = settings.lake_root / "artifacts" / "wc_predictor" / "manifest.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_inplay_coefficients() -> dict[str, Any]:
    path = settings.lake_root / "artifacts" / "inplay_coefficients.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _best_wc_metric(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not metrics:
        return {}
    best = min(metrics, key=lambda m: m.get("brier", 1.0))
    return {
        "model": best.get("model"),
        "accuracy": _round4(best.get("accuracy")),
        "brier": _round4(best.get("brier")),
        "log_loss": _round4(best.get("log_loss")),
        "weights": best.get("weights"),
    }


def _build_snapshot(
    *,
    source: str,
    wc_report: dict[str, Any] | None = None,
    inplay_report: dict[str, Any] | None = None,
    walkforward_report: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    ts = timestamp or datetime.now(UTC).isoformat()
    run_id = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%SZ")
    manifest = manifest or _load_manifest()
    coeffs = _load_inplay_coefficients()

    train_metrics = manifest.get("training_metrics") or {}
    collab = manifest.get("collab_metrics") or {}
    ensemble = manifest.get("ensemble_weights") or {}

    wc_best = _best_wc_metric((wc_report or {}).get("metrics") or [])
    live = (inplay_report or {}).get("live_ticks") or {}
    wf_inplay = (inplay_report or {}).get("walkforward") or {}
    wf_wc = walkforward_report or {}
    wf_summary = wf_wc.get("summary") or {}
    recon = (inplay_report or {}).get("reconciliation") or {}

    snapshot = {
        "run_id": run_id,
        "timestamp": ts,
        "source": source,
        "metrics": {
            "wc_pregame": {
                "eval_season": (wc_report or {}).get("eval_season"),
                "eval_samples": (wc_report or {}).get("eval_samples"),
                "benchmark_best_model": wc_best.get("model"),
                "benchmark_accuracy": wc_best.get("accuracy"),
                "benchmark_brier": wc_best.get("brier"),
                "benchmark_log_loss": wc_best.get("log_loss"),
                "artifact_created_at": manifest.get("created_at"),
                "artifact_holdout_accuracy": _round4(train_metrics.get("holdout_accuracy")),
                "artifact_brier": _round4(collab.get("brier_score")),
                "ensemble_dixon_coles": ensemble.get("dixon_coles"),
                "ensemble_logistic": ensemble.get("logistic"),
                "fixture_rows": manifest.get("fixture_rows"),
            },
            "wc_walkforward": {
                "editions_evaluated": wf_wc.get("editions_evaluated"),
                "mean_accuracy": _round4(wf_summary.get("mean_accuracy")),
                "mean_brier": _round4(wf_summary.get("mean_brier")),
                "worst_brier_season": wf_summary.get("worst_brier_season"),
                "best_brier_season": wf_summary.get("best_brier_season"),
            },
            "inplay": {
                "live_brier_modelo": _round4(live.get("brier_modelo")),
                "live_brier_mercado": _round4(live.get("brier_mercado")),
                "live_delta_brier": _round4(live.get("delta_brier")),
                "live_accuracy": _round4(live.get("accuracy_modelo")),
                "n_live_events": live.get("n_events"),
                "n_live_ticks": live.get("n_ticks"),
                "walkforward_brier": _round4(wf_inplay.get("brier_overall")),
                "walkforward_baseline_brier": _round4(coeffs.get("holdout_brier_baseline")),
                "coefficients_trained_at": coeffs.get("trained_at"),
            },
            "reconciliation": {
                "n_bets": recon.get("n_bets"),
                "hit_rate": _round4(recon.get("hit_rate")),
                "pnl": recon.get("pnl"),
                "brier_avg": _round4(recon.get("brier_avg")),
            },
        },
    }
    return snapshot


def load_history() -> dict[str, Any]:
    if not HISTORY_PATH.exists():
        return {"updated_at": None, "snapshots": []}
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(history: dict[str, Any]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history["updated_at"] = datetime.now(UTC).isoformat()
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def append_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    history = load_history()
    snapshots: list[dict[str, Any]] = history.setdefault("snapshots", [])

    if snapshots and snapshots[-1].get("run_id") == snapshot.get("run_id"):
        snapshots[-1] = snapshot
    else:
        snapshots.append(snapshot)

    snapshots.sort(key=lambda s: s.get("timestamp", ""))
    save_history(history)
    LATEST_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return history


def _snapshot_from_full_improvement(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = data.get("finished_at") or data.get("started_at")
    if not ts:
        return None

    steps = data.get("steps") or {}
    train_wc = steps.get("train_wc") or {}
    train_gbm = steps.get("train_gbm") or {}
    tune = steps.get("tune_inplay") or {}
    wf = steps.get("walkforward_wc") or {}
    bench = data.get("benchmark") or {}

    manifest = {
        "created_at": train_wc.get("created_at"),
        "fixture_rows": train_wc.get("fixture_rows"),
        "training_metrics": {"holdout_accuracy": train_wc.get("holdout_accuracy")},
        "collab_metrics": {"brier_score": train_wc.get("ensemble_brier")},
        "ensemble_weights": train_wc.get("ensemble_weights") or {},
    }

    inplay_report = {
        "live_ticks": bench.get("live_ticks") or {},
        "walkforward": bench.get("walkforward") or {},
        "reconciliation": bench.get("reconciliation") or {},
    }

    snapshot = _build_snapshot(
        source="full_improvement",
        wc_report=None,
        inplay_report=inplay_report,
        walkforward_report=wf,
        manifest=manifest,
        timestamp=ts,
    )
    snapshot["metrics"]["gbm"] = {
        "val_accuracy": _round4(train_gbm.get("val_accuracy")),
        "val_logloss": _round4(train_gbm.get("val_logloss")),
    }
    snapshot["metrics"]["inplay"]["tune_holdout_brier"] = _round4(tune.get("holdout_brier"))
    snapshot["metrics"]["inplay"]["tune_gain"] = _round4(tune.get("gain"))
    return snapshot


def _snapshot_from_wc_benchmark(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = data.get("generated_at")
    if not ts:
        return None
    return _build_snapshot(
        source="wc_benchmark",
        wc_report=data,
        inplay_report=None,
        walkforward_report=None,
        manifest=_load_manifest(),
        timestamp=ts,
    )


def seed_history(*, force: bool = False) -> dict[str, Any]:
    history = load_history()
    if history.get("snapshots") and not force:
        return history

    seeds: list[dict[str, Any]] = []
    reports_dir = settings.lake_root / "reports"

    for path in sorted(reports_dir.glob("full_improvement_*.json")):
        snap = _snapshot_from_full_improvement(path)
        if snap:
            seeds.append(snap)

    wc_bench = _snapshot_from_wc_benchmark(reports_dir / "wc_benchmark_report.json")
    if wc_bench:
        seeds.append(wc_bench)

    wf_path = reports_dir / "wc_walkforward_report.json"
    if wf_path.exists() and not any(s.get("source") == "full_improvement" for s in seeds):
        data = json.loads(wf_path.read_text(encoding="utf-8"))
        snap = _build_snapshot(
            source="wc_walkforward",
            walkforward_report=data,
            timestamp=data.get("generated_at"),
        )
        seeds.append(snap)

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for snap in sorted(seeds, key=lambda s: s.get("timestamp", "")):
        key = snap.get("run_id") or snap.get("timestamp")
        if key in seen:
            continue
        seen.add(key)
        unique.append(snap)

    history["snapshots"] = unique
    save_history(history)
    if unique:
        LATEST_PATH.write_text(json.dumps(unique[-1], ensure_ascii=False, indent=2), encoding="utf-8")
    return history


def run_model_benchmark(
    *,
    eval_season: int | None = None,
    skip_walkforward: bool = False,
    skip_wc_benchmark: bool = False,
    walkforward_max_editions: int = 6,
    user_id: str = "jamarorn",
) -> dict[str, Any]:
    eval_season = eval_season if eval_season is not None else settings.wc_validation_season

    wc_report: dict[str, Any] | None = None
    if not skip_wc_benchmark:
        from pipelines.wc_benchmark import run_benchmark

        wc_report = run_benchmark(eval_season=eval_season, enable_mlflow=False)
        out = settings.lake_root / "reports" / "wc_benchmark_report.json"
        out.write_text(json.dumps(wc_report, ensure_ascii=False, indent=2), encoding="utf-8")

    from pipelines.inplay_benchmark import full_benchmark_report

    inplay_report = full_benchmark_report(
        eval_season=eval_season,
        verbose=False,
        live_only=skip_walkforward,
    )
    inplay_out = settings.lake_root / "reports" / "inplay_benchmark_report.json"
    inplay_out.write_text(json.dumps(inplay_report, ensure_ascii=False, indent=2), encoding="utf-8")

    walkforward_report: dict[str, Any] | None = None
    if not skip_walkforward:
        from pipelines.wc_walkforward import run_walkforward

        walkforward_report = run_walkforward(max_editions=walkforward_max_editions)
        wf_out = settings.lake_root / "reports" / "wc_walkforward_report.json"
        wf_out.write_text(json.dumps(walkforward_report, ensure_ascii=False, indent=2), encoding="utf-8")

    snapshot = _build_snapshot(
        source="run-model-benchmark",
        wc_report=wc_report,
        inplay_report=inplay_report,
        walkforward_report=walkforward_report,
    )

    history = append_snapshot(snapshot)
    return {
        "snapshot": snapshot,
        "history_size": len(history.get("snapshots", [])),
        "history_path": str(HISTORY_PATH),
    }


def _fill_walkforward_from_report(metrics: dict[str, Any]) -> None:
    """Preenche walkforward ausente a partir do relatório salvo."""
    wf = metrics.get("wc_walkforward") or {}
    if wf.get("mean_accuracy") is not None:
        return
    wf_path = settings.lake_root / "reports" / "wc_walkforward_report.json"
    if not wf_path.exists():
        return
    data = json.loads(wf_path.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}
    wf.update(
        {
            "editions_evaluated": data.get("editions_evaluated"),
            "mean_accuracy": _round4(summary.get("mean_accuracy")),
            "mean_brier": _round4(summary.get("mean_brier")),
            "worst_brier_season": summary.get("worst_brier_season"),
            "best_brier_season": summary.get("best_brier_season"),
        }
    )
    metrics["wc_walkforward"] = wf


def history_with_deltas() -> dict[str, Any]:
    """Histórico enriquecido com delta vs snapshot anterior."""
    history = load_history()
    snapshots = history.get("snapshots") or []
    enriched: list[dict[str, Any]] = []

    metric_paths = [
        ("wc_pregame", "artifact_holdout_accuracy"),
        ("wc_pregame", "artifact_brier"),
        ("wc_pregame", "benchmark_brier"),
        ("wc_walkforward", "mean_accuracy"),
        ("wc_walkforward", "mean_brier"),
        ("inplay", "live_brier_modelo"),
        ("inplay", "live_delta_brier"),
        ("inplay", "walkforward_brier"),
        ("reconciliation", "hit_rate"),
        ("reconciliation", "pnl"),
    ]

    for i, snap in enumerate(snapshots):
        row = dict(snap)
        deltas: dict[str, float | None] = {}
        if i > 0:
            prev = snapshots[i - 1]["metrics"]
            curr = snap["metrics"]
            for section, key in metric_paths:
                prev_val = (prev.get(section) or {}).get(key)
                curr_val = (curr.get(section) or {}).get(key)
                if prev_val is not None and curr_val is not None:
                    deltas[f"{section}.{key}"] = round(float(curr_val) - float(prev_val), 4)
        row["deltas"] = deltas
        enriched.append(row)

    latest = enriched[-1] if enriched else None
    if latest:
        _fill_walkforward_from_report(latest.setdefault("metrics", {}))
    return {
        "updated_at": history.get("updated_at"),
        "latest": latest,
        "snapshots": enriched,
        "summary_labels": {
            "wc_pregame.artifact_holdout_accuracy": "WC holdout acc",
            "wc_pregame.artifact_brier": "WC Brier artefato",
            "wc_pregame.benchmark_brier": "WC Brier benchmark",
            "wc_walkforward.mean_accuracy": "Walkforward acc média",
            "wc_walkforward.mean_brier": "Walkforward Brier média",
            "inplay.live_brier_modelo": "In-play Brier (live)",
            "inplay.live_delta_brier": "In-play vs mercado",
            "inplay.walkforward_brier": "In-play Brier (WF)",
            "reconciliation.hit_rate": "Hit rate apostas",
            "reconciliation.pnl": "P&L apostas (R$)",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark consolidado + histórico de evolução")
    parser.add_argument("--eval-season", type=int, default=settings.wc_validation_season)
    parser.add_argument("--skip-walkforward", action="store_true", help="Pula walk-forward WC/in-play (mais rápido)")
    parser.add_argument("--skip-wc-benchmark", action="store_true", help="Pula benchmark de modelos WC")
    parser.add_argument("--seed-only", action="store_true", help="Só reconstrói histórico a partir de relatórios existentes")
    parser.add_argument("--force-seed", action="store_true", help="Recria histórico mesmo se já existir")
    args = parser.parse_args()

    if args.seed_only:
        history = seed_history(force=args.force_seed)
        print(f"Histórico: {len(history.get('snapshots', []))} snapshots em {HISTORY_PATH}")
        return

    seed_history(force=False)
    result = run_model_benchmark(
        eval_season=args.eval_season,
        skip_walkforward=args.skip_walkforward,
        skip_wc_benchmark=args.skip_wc_benchmark,
    )
    snap = result["snapshot"]["metrics"]
    print(f"\nBenchmark salvo. Histórico: {result['history_size']} entradas")
    print(f"  WC holdout acc:     {snap['wc_pregame'].get('artifact_holdout_accuracy')}")
    print(f"  WC Brier benchmark: {snap['wc_pregame'].get('benchmark_brier')}")
    print(f"  In-play Brier live: {snap['inplay'].get('live_brier_modelo')} (Δ mercado {snap['inplay'].get('live_delta_brier')})")
    if snap["wc_walkforward"].get("mean_brier"):
        print(f"  Walkforward Brier:  {snap['wc_walkforward'].get('mean_brier')}")
    print(f"  Arquivo: {result['history_path']}")


if __name__ == "__main__":
    main()
