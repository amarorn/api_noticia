"""Relatório semanal in-play: retune NHPP, walk-forward e retreino GBM (WS1).

Sequência padrão (domingo):
1. ``tune-inplay --source both`` — recalibra coeficientes MLE
2. ``evaluate_inplay`` walk-forward + A/B momentum
3. ``train-inplay-gbm`` — retreino LightGBM

CLI: inplay-weekly-report [--skip-tune] [--skip-gbm] [--skip-walkforward]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from pipelines.inplay_benchmark import compute_ab_momentum_report, compute_walkforward_brier
from pipelines.inplay_daily_report import (
    METRICS_HISTORY_PATH,
    REPORTS_DIR,
    append_metrics_row,
)

WEEKLY_BASELINE_PATH = REPORTS_DIR / "inplay_weekly_baseline.json"


def _report_path_for(week_ending: date) -> Path:
    return REPORTS_DIR / f"inplay_weekly_{week_ending.strftime('%Y%m%d')}.json"


def _serialize(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    return obj


def run_tune_step(
    *,
    eval_season: int,
    verbose: bool = False,
) -> dict[str, Any]:
    """Recalibra coeficientes MLE (fixtures + ticks)."""
    from pipelines.wc_inplay_tune import run_inplay_tune

    try:
        coefs = run_inplay_tune(
            eval_season=eval_season,
            verbose=verbose,
            source="both",
        )
        return {
            "ok": True,
            "n_observations": coefs.n_observations,
            "holdout_brier": coefs.holdout_brier,
            "holdout_brier_baseline": coefs.holdout_brier_baseline,
            "dataset_hash": coefs.dataset_hash,
            "gain": round(
                (coefs.holdout_brier_baseline or 0) - (coefs.holdout_brier or 0),
                5,
            )
            if coefs.holdout_brier_baseline is not None and coefs.holdout_brier is not None
            else None,
        }
    except (ValueError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def run_gbm_train_step(
    *,
    val_season: int,
    verbose: bool = False,
) -> dict[str, Any]:
    """Retreina GBM in-play walk-forward."""
    from pipelines.wc_inplay_gbm_train import run_gbm_training

    try:
        result = run_gbm_training(val_season=val_season)
        payload = {
            "ok": True,
            "val_accuracy": round(result.val_accuracy, 4),
            "val_logloss": round(result.val_logloss, 4),
            "train_logloss": round(result.train_logloss, 4),
            "n_train": result.n_train,
            "n_val": result.n_val,
        }
        if verbose:
            print(
                f"GBM: val_acc={payload['val_accuracy']:.3f} "
                f"val_logloss={payload['val_logloss']:.4f}"
            )
        return payload
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


def run_walkforward_step(
    *,
    eval_season: int,
    n_simulations: int = 2000,
    include_ab_momentum: bool = True,
    verbose: bool = False,
) -> dict[str, Any]:
    """Walk-forward in-play (calibrado + A/B momentum)."""
    default_wf = compute_walkforward_brier(
        eval_season=eval_season,
        n_simulations=n_simulations,
        use_momentum=True,
        use_calibrated_coefficients=True,
        verbose=verbose,
    )
    baseline_wf = compute_walkforward_brier(
        eval_season=eval_season,
        n_simulations=n_simulations,
        use_momentum=True,
        use_calibrated_coefficients=False,
        verbose=False,
    )
    out: dict[str, Any] = {
        "eval_season": eval_season,
        "calibrated": default_wf,
        "baseline_coefficients": baseline_wf,
    }
    if include_ab_momentum:
        out["ab_momentum"] = compute_ab_momentum_report(
            eval_season=eval_season,
            n_simulations=n_simulations,
            verbose=verbose,
        )
    return out


def build_weekly_report(
    *,
    week_ending: date | None = None,
    eval_season: int = 2022,
    skip_tune: bool = False,
    skip_gbm: bool = False,
    skip_walkforward: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Monta relatório semanal consolidado."""
    end = week_ending or datetime.now(UTC).date()
    ts = datetime.now(UTC).isoformat()

    tune: dict[str, Any] | None = None
    if not skip_tune:
        if verbose:
            print("=== TUNE IN-PLAY (MLE fixtures + ticks) ===")
        tune = run_tune_step(eval_season=eval_season, verbose=verbose)

    walkforward: dict[str, Any] | None = None
    if not skip_walkforward:
        if verbose:
            print("\n=== WALK-FORWARD IN-PLAY ===")
        walkforward = run_walkforward_step(eval_season=eval_season, verbose=verbose)

    gbm: dict[str, Any] | None = None
    if not skip_gbm:
        if verbose:
            print("\n=== RETREINO GBM ===")
        gbm = run_gbm_train_step(val_season=eval_season, verbose=verbose)

    wf_cal = (walkforward or {}).get("calibrated") or {}
    wf_base = (walkforward or {}).get("baseline_coefficients") or {}

    report: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": "weekly",
        "week_ending": str(end),
        "generated_at": ts,
        "eval_season": eval_season,
        "tune": tune,
        "walkforward": walkforward,
        "gbm_train": gbm,
        "summary": {
            "walkforward_brier": wf_cal.get("brier_overall"),
            "walkforward_brier_baseline": wf_base.get("brier_overall"),
            "walkforward_n_samples": wf_cal.get("n_samples"),
            "tune_holdout_brier": (tune or {}).get("holdout_brier"),
            "tune_n_observations": (tune or {}).get("n_observations"),
            "gbm_val_accuracy": (gbm or {}).get("val_accuracy"),
            "gbm_val_logloss": (gbm or {}).get("val_logloss"),
        },
    }
    return report


def _metrics_row_from_weekly(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") or {}
    return {
        "report_kind": "weekly",
        "report_date": report.get("week_ending"),
        "generated_at": report.get("generated_at"),
        "walkforward_brier": summary.get("walkforward_brier"),
        "walkforward_brier_baseline": summary.get("walkforward_brier_baseline"),
        "walkforward_n_samples": summary.get("walkforward_n_samples"),
        "tune_holdout_brier": summary.get("tune_holdout_brier"),
        "tune_n_observations": summary.get("tune_n_observations"),
        "gbm_val_accuracy": summary.get("gbm_val_accuracy"),
        "gbm_val_logloss": summary.get("gbm_val_logloss"),
    }


def save_weekly_report(report: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _report_path_for(date.fromisoformat(str(report["week_ending"])))
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=_serialize),
        encoding="utf-8",
    )
    return path


def seed_weekly_baseline_if_missing(report: dict[str, Any], *, min_samples: int = 100) -> bool:
    if WEEKLY_BASELINE_PATH.is_file():
        return False
    summary = report.get("summary") or {}
    brier = summary.get("walkforward_brier")
    n = summary.get("walkforward_n_samples") or 0
    if brier is None or n < min_samples:
        return False
    payload = {
        "created_at": report.get("generated_at"),
        "week_ending": report.get("week_ending"),
        "walkforward_brier": brier,
        "note": "Baseline semanal congelado na primeira execução walk-forward com amostra suficiente.",
    }
    WEEKLY_BASELINE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def check_weekly_regression(
    report: dict[str, Any],
    *,
    max_brier_degradation: float = 0.05,
) -> tuple[bool, list[str]]:
    """Compara walk-forward Brier vs baseline semanal ou último relatório."""
    messages: list[str] = []
    failures: list[str] = []
    summary = report.get("summary") or {}
    brier = summary.get("walkforward_brier")

    if brier is None:
        err = (report.get("walkforward") or {}).get("calibrated", {}).get("error")
        if err:
            messages.append(f"Aviso: walk-forward falhou — {err}")
        else:
            messages.append("Aviso: walkforward_brier ausente — gate ignorado.")
        return True, messages

    brier_val = float(brier)
    refs: list[tuple[str, float]] = []

    if WEEKLY_BASELINE_PATH.is_file():
        baseline = json.loads(WEEKLY_BASELINE_PATH.read_text(encoding="utf-8"))
        base = baseline.get("walkforward_brier")
        if base is not None:
            refs.append(("baseline_semanal", float(base)))

    if METRICS_HISTORY_PATH.is_file():
        import pandas as pd

        df = pd.read_parquet(METRICS_HISTORY_PATH)
        if "report_kind" in df.columns:
            weekly = df[df["report_kind"] == "weekly"].dropna(subset=["walkforward_brier"])
        else:
            weekly = df.dropna(subset=["walkforward_brier"]) if "walkforward_brier" in df.columns else pd.DataFrame()
        week = str(report.get("week_ending", ""))
        if not weekly.empty and "report_date" in weekly.columns:
            weekly = weekly[weekly["report_date"].astype(str) != week]
        if not weekly.empty:
            last = float(weekly.iloc[-1]["walkforward_brier"])
            refs.append(("ultimo_semanal", last))

    for label, ref in refs:
        if ref <= 0:
            continue
        rel = (brier_val - ref) / ref
        messages.append(f"Walk-forward Brier {brier_val:.5f} vs {label} {ref:.5f} (Δ {rel:+.1%})")
        if rel > max_brier_degradation:
            failures.append(
                f"Walk-forward piorou {rel:.1%} vs {label} (limite +{max_brier_degradation:.0%})"
            )

    ok = len(failures) == 0
    if failures:
        messages.extend(f"FALHA: {f}" for f in failures)
    else:
        messages.append("OK: walk-forward sem regressão detectada.")
    return ok, messages


def run_weekly_report(
    *,
    week_ending: date | None = None,
    eval_season: int = 2022,
    skip_tune: bool = False,
    skip_gbm: bool = False,
    skip_walkforward: bool = False,
    verbose: bool = False,
    append_history: bool = True,
) -> dict[str, Any]:
    report = build_weekly_report(
        week_ending=week_ending,
        eval_season=eval_season,
        skip_tune=skip_tune,
        skip_gbm=skip_gbm,
        skip_walkforward=skip_walkforward,
        verbose=verbose,
    )
    save_weekly_report(report)
    if append_history:
        append_metrics_row(_metrics_row_from_weekly(report))
    seed_weekly_baseline_if_missing(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Relatório semanal in-play (tune + WF + GBM)")
    parser.add_argument("--week-ending", type=str, help="Data fim da semana (YYYY-MM-DD)")
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--skip-tune", action="store_true")
    parser.add_argument("--skip-gbm", action="store_true")
    parser.add_argument("--skip-walkforward", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args()

    week = date.fromisoformat(args.week_ending) if args.week_ending else None
    verbose = not args.quiet and not args.json

    report = run_weekly_report(
        week_ending=week,
        eval_season=args.eval_season,
        skip_tune=args.skip_tune,
        skip_gbm=args.skip_gbm,
        skip_walkforward=args.skip_walkforward,
        verbose=verbose,
        append_history=not args.no_history,
    )

    ok, gate_msgs = check_weekly_regression(report)

    if args.json:
        print(json.dumps({"report": report, "regression_gate": {"ok": ok, "messages": gate_msgs}}, indent=2, default=_serialize))
    elif not args.quiet:
        s = report.get("summary") or {}
        print(f"Relatório: {_report_path_for(date.fromisoformat(str(report['week_ending'])))}")
        print(f"  Walk-forward Brier: {s.get('walkforward_brier')} (n={s.get('walkforward_n_samples')})")
        for line in gate_msgs:
            print(f"  {line}")

    if not ok:
        return 1
    wf_err = (report.get("walkforward") or {}).get("calibrated", {}).get("error")
    if wf_err and report.get("summary", {}).get("walkforward_brier") is None:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
