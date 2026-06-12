"""Pipeline completo: aprimoramento dos modelos WC + in-play com dados coletados.

Etapas:
1. Inventário do lake (live ticks, eventos Superbet, reconciliação)
2. Reconciliação carteira → silver
3. Retreino GBM com feedback real (Fase 4)
4. Treino GBM in-play walk-forward (Fase 3)
5. Calibração coeficientes momentum/NHPP (Fase 2)
6. Retreino predictor WC (ensemble pré-jogo) — opcional
7. Palpites completos Copa 2026 (72 jogos)
8. Benchmark in-play + walk-forward

CLI: run-full-improvement [--skip-wc-retrain] [--user jamarorn]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from config import settings

log = structlog.get_logger()


@dataclass
class ImprovementReport:
    started_at: str
    inventory: dict[str, Any] = field(default_factory=dict)
    steps: dict[str, Any] = field(default_factory=dict)
    predictions_summary: dict[str, Any] | None = None
    benchmark: dict[str, Any] | None = None
    finished_at: str | None = None
    errors: list[str] = field(default_factory=list)


def _inventory() -> dict[str, Any]:
    import pandas as pd

    inv: dict[str, Any] = {}
    ticks_path = settings.bronze_path / "superbet" / "live_ticks.parquet"
    if ticks_path.exists():
        df = pd.read_parquet(ticks_path)
        inv["live_ticks"] = {
            "rows": len(df),
            "events": int(df["event_id"].nunique()) if "event_id" in df.columns else 0,
            "path": str(ticks_path),
        }

    events_dir = settings.bronze_path / "superbet" / "events"
    if events_dir.exists():
        inv["superbet_events"] = len([d for d in events_dir.iterdir() if d.is_dir()])

    reg = settings.lake_root / "artifacts" / "superbet_finalized_events.json"
    if reg.exists():
        data = json.loads(reg.read_text(encoding="utf-8"))
        inv["finalized_events"] = len(data.get("events", {}))

    recon_dir = settings.silver_path / "bet_reconciliation"
    if recon_dir.exists():
        for p in recon_dir.glob("*.parquet"):
            df = pd.read_parquet(p)
            inv[f"reconciliation_{p.stem}"] = len(df)

    manifest = settings.wc_artifact_dir / "manifest.json"
    if manifest.exists():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        inv["wc_predictor"] = {
            "created_at": m.get("created_at"),
            "fixture_rows": m.get("fixture_rows"),
            "holdout_accuracy": (m.get("training_metrics") or {}).get("holdout_accuracy"),
        }
    return inv


def _step_reconcile(user_id: str) -> dict[str, Any]:
    from pipelines.inplay_benchmark import compute_reconciliation_metrics
    from pipelines.user_bet_reconciliation import reconcile_user_transactions, save_reconciliation

    df = reconcile_user_transactions(user_id)
    if df.empty:
        return {"status": "empty", "user_id": user_id}
    path = save_reconciliation(df, user_id)
    metrics = compute_reconciliation_metrics(user_id)
    return {"status": "ok", "n_pairs": len(df), "path": str(path), **metrics}


def _step_feedback_retrain(user_id: str, min_confidence: float) -> dict[str, Any]:
    from pipelines.feedback_retrain import retrain_with_feedback

    result = retrain_with_feedback(user_id=user_id, min_confidence=min_confidence)
    return asdict(result)


def _step_train_gbm() -> dict[str, Any]:
    from pipelines.wc_inplay_gbm_train import run_gbm_training

    result = run_gbm_training(seed=42)
    return {
        "train_logloss": result.train_logloss,
        "val_logloss": result.val_logloss,
        "val_accuracy": result.val_accuracy,
        "n_train": result.n_train,
        "n_val": result.n_val,
        "top_features": dict(
            sorted(result.feature_importance.items(), key=lambda x: -x[1])[:5]
        ),
    }


def _step_tune_inplay() -> dict[str, Any]:
    from pipelines.wc_inplay_tune import run_inplay_tune

    coefs = run_inplay_tune(verbose=False)
    return {
        "holdout_brier": coefs.holdout_brier,
        "holdout_brier_baseline": coefs.holdout_brier_baseline,
        "n_observations": coefs.n_observations,
        "gain": round(
            (coefs.holdout_brier_baseline or 0) - (coefs.holdout_brier or 0), 5
        ),
    }


def _step_train_wc() -> dict[str, Any]:
    from models.wc_artifact import load_or_train_wc_predictor

    predictor, manifest = load_or_train_wc_predictor(force=True, allow_train=True)
    return {
        "created_at": manifest.get("created_at"),
        "fixture_rows": manifest.get("fixture_rows"),
        "holdout_accuracy": (manifest.get("training_metrics") or {}).get("holdout_accuracy"),
        "ensemble_brier": (manifest.get("collab_metrics") or {}).get("brier_score"),
        "ensemble_weights": manifest.get("ensemble_weights"),
    }


def _step_predict_wc_round(round_file: Path) -> dict[str, Any]:
    from models.wc_artifact import load_or_train_wc_predictor
    from schemas.national_teams import normalize_national_team

    round_data = json.loads(round_file.read_text(encoding="utf-8"))
    predictor, _ = load_or_train_wc_predictor(force=False, allow_train=False)

    preds = []
    for match in round_data.get("matches", []):
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        phase = match.get("phase", round_data.get("phase", "group"))
        p = predictor.predict(home, away, phase=phase, is_neutral=True)
        preds.append(
            {
                "match_id": match.get("id"),
                "home_team": home,
                "away_team": away,
                "group": match.get("group"),
                "round": match.get("round"),
                "kickoff": match.get("kickoff"),
                "prediction": p.prediction,
                "confidence": round(p.confidence, 4),
                "prob_home": round(p.prob_home, 4),
                "prob_draw": round(p.prob_draw, 4),
                "prob_away": round(p.prob_away, 4),
                "poisson_score": p.poisson_score,
            }
        )

    out_dir = settings.lake_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"wc_2026_predictions_{ts}.json"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "competition": round_data.get("competition"),
        "season": round_data.get("season"),
        "n_matches": len(preds),
        "predictions": preds,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    dist = {"1": 0, "X": 0, "2": 0}
    for p in preds:
        dist[p["prediction"]] = dist.get(p["prediction"], 0) + 1
    avg_conf = sum(p["confidence"] for p in preds) / len(preds) if preds else 0

    return {
        "n_matches": len(preds),
        "distribution": dist,
        "avg_confidence": round(avg_conf, 4),
        "output_path": str(out_path),
    }


def _step_benchmark(*, live_only: bool = False) -> dict[str, Any]:
    from pipelines.inplay_benchmark import full_benchmark_report

    return full_benchmark_report(eval_season=2022, live_only=live_only, verbose=False)


def _step_walkforward(max_editions: int = 6) -> dict[str, Any]:
    from pipelines.wc_walkforward import run_walkforward

    return run_walkforward(max_editions=max_editions)


def run_full_improvement(
    *,
    user_id: str = "jamarorn",
    min_confidence: float = 0.7,
    skip_wc_retrain: bool = False,
    skip_walkforward: bool = False,
    round_file: Path | None = None,
) -> ImprovementReport:
    report = ImprovementReport(started_at=datetime.now(UTC).isoformat())
    round_file = round_file or Path("data/rounds/wc_2026.json")

    print("\n=== 1/8 Inventário ===")
    report.inventory = _inventory()
    print(json.dumps(report.inventory, indent=2, ensure_ascii=False))

    steps = [
        ("reconcile", lambda: _step_reconcile(user_id)),
        ("feedback_gbm", lambda: _step_feedback_retrain(user_id, min_confidence)),
        ("train_gbm", _step_train_gbm),
        ("tune_inplay", _step_tune_inplay),
    ]
    if not skip_wc_retrain:
        steps.append(("train_wc", _step_train_wc))

    for i, (name, fn) in enumerate(steps, start=2):
        print(f"\n=== {i}/8 {name} ===")
        try:
            report.steps[name] = fn()
            print(json.dumps(report.steps[name], indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            log.exception("step_failed", step=name, error=str(exc))
            report.steps[name] = {"error": str(exc)}
            report.errors.append(f"{name}: {exc}")

    print("\n=== Palpites Copa 2026 (72 jogos) ===")
    try:
        report.predictions_summary = _step_predict_wc_round(round_file)
        print(json.dumps(report.predictions_summary, indent=2, ensure_ascii=False))
    except Exception as exc:
        report.errors.append(f"predict_wc: {exc}")
        print(f"ERRO palpites: {exc}")

    print("\n=== Benchmark in-play ===")
    try:
        report.benchmark = _step_benchmark(live_only=False)
        lt = report.benchmark.get("live_ticks", {})
        if lt.get("brier_modelo"):
            print(f"  Brier live ticks: {lt['brier_modelo']:.4f} ({lt.get('n_ticks', 0)} ticks)")
        wf = report.benchmark.get("walkforward", {})
        if wf.get("brier_overall"):
            print(f"  Brier walk-forward: {wf['brier_overall']:.4f}")
    except Exception as exc:
        report.errors.append(f"benchmark: {exc}")
        print(f"ERRO benchmark: {exc}")

    if not skip_walkforward:
        print("\n=== Walk-forward WC (edições históricas) ===")
        try:
            report.steps["walkforward_wc"] = _step_walkforward(max_editions=6)
            print(json.dumps(report.steps["walkforward_wc"], indent=2, ensure_ascii=False, default=str))
        except Exception as exc:
            report.errors.append(f"walkforward: {exc}")
            print(f"ERRO walkforward: {exc}")

    report.finished_at = datetime.now(UTC).isoformat()
    out_dir = settings.lake_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = out_dir / f"full_improvement_{ts}.json"
    report_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\nRelatório salvo: {report_path}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aprimoramento completo WC + in-play com dados coletados"
    )
    parser.add_argument("--user", default="jamarorn", help="user_id da carteira Superbet")
    parser.add_argument("--min-confidence", type=float, default=0.7)
    parser.add_argument(
        "--skip-wc-retrain",
        action="store_true",
        help="Pula train-wc --force (~5–15 min); usa artifact existente nos palpites",
    )
    parser.add_argument("--skip-walkforward", action="store_true")
    parser.add_argument(
        "--round-file",
        type=Path,
        default=Path("data/rounds/wc_2026.json"),
    )
    args = parser.parse_args()

    report = run_full_improvement(
        user_id=args.user,
        min_confidence=args.min_confidence,
        skip_wc_retrain=args.skip_wc_retrain,
        skip_walkforward=args.skip_walkforward,
        round_file=args.round_file,
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
