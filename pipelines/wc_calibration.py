"""Estudo LGN: calibração + bootstrap na temporada de validação (Copa).

Inclui avaliação ECE pré/pós do calibrador Platt (Fase 0.1).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from models.economics import (
    bootstrap_accuracy_ci,
    calibration_by_predicted_class,
    ces_blend_probabilities,
    lgn_min_sample_warning,
)
from models.wc_calibrator import WcCalibrator, compute_ece
from models.wc_collaborative import CollaborativeWcModel
from pipelines.wc_benchmark import LABELS, _build_eval_rows


def run_calibration_study(validation_season: int | None = None) -> dict:
    season = validation_season or settings.wc_validation_season
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Sem dados de Copa. Execute: import-world-cup")

    _, y_true, rows = _build_eval_rows(fixtures, season)
    warning = lgn_min_sample_warning(len(rows), f"validação Copa {season}")

    y_pred_p = [LABELS[int(np.argmax(r.probs_poisson))] for r in rows]
    conf_p = [float(max(r.probs_poisson)) for r in rows]
    acc_ci_p = bootstrap_accuracy_ci(y_true, y_pred_p)
    cal_bins_p = calibration_by_predicted_class(y_true, y_pred_p, conf_p)

    collab = CollaborativeWcModel()
    collab_metrics = collab.fit(fixtures, validation_season=season)
    pw, lw = collab.poisson_weight, collab.logistic_weight

    y_pred_e: list[str] = []
    conf_e: list[float] = []
    for r in rows:
        models = {
            "poisson": dict(zip(LABELS, r.probs_poisson, strict=True)),
            "logistic": dict(zip(LABELS, r.probs_logistic or [0, 0, 0], strict=True)),
        }
        probs = ces_blend_probabilities(
            models, weights={"poisson": pw, "logistic": lw}, sigma=settings.dixit_sigma
        )
        pred = max(probs, key=probs.get)  # type: ignore[arg-type]
        y_pred_e.append(pred)
        conf_e.append(float(probs[pred]))

    acc_ci_e = bootstrap_accuracy_ci(y_true, y_pred_e)
    cal_bins_e = calibration_by_predicted_class(y_true, y_pred_e, conf_e)

    # --- Fase 0.1: ECE pré/pós com calibrador Platt ---
    probs_ensemble_raw = np.array([
        [
            pw * r.probs_poisson[0] + lw * (r.probs_logistic[0] if r.probs_logistic else 0),
            pw * r.probs_poisson[1] + lw * (r.probs_logistic[1] if r.probs_logistic else 0),
            pw * r.probs_poisson[2] + lw * (r.probs_logistic[2] if r.probs_logistic else 0),
        ]
        for r in rows
    ])
    # Normalizar por linha
    row_sums = probs_ensemble_raw.sum(axis=1, keepdims=True)
    row_sums = np.maximum(row_sums, 1e-9)
    probs_ensemble_raw = probs_ensemble_raw / row_sums
    y_true_arr = np.array(y_true)

    ece_before = compute_ece(probs_ensemble_raw, y_true_arr)
    calibrator = WcCalibrator()
    cal_metrics = calibrator.fit(probs_ensemble_raw, y_true_arr)
    probs_calibrated = calibrator.calibrate(probs_ensemble_raw)
    ece_after = compute_ece(probs_calibrated, y_true_arr)

    platt_section = {
        "method": cal_metrics.method,
        "n_samples": cal_metrics.n_samples,
        "ece_before": round(ece_before, 6),
        "ece_after": round(ece_after, 6),
        "ece_reduction_pct": round((1 - ece_after / max(ece_before, 1e-9)) * 100, 1),
        "brier_before": cal_metrics.brier_before,
        "brier_after": cal_metrics.brier_after,
    }

    def _chart_points(bins: list[dict]) -> list[dict]:
        return [
            {
                "confidence_pct": round(b["mean_confidence"] * 100, 1),
                "observed_pct": round(b["observed_hit_rate"] * 100, 1),
                "n": b["n"],
            }
            for b in bins
        ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "framework": {
            "lgn": "bootstrap + calibração no holdout",
            "coase": "value-wc-odds usa min_edge efetivo (margem + custo)",
            "dixit_stiglitz": "WcPredictor combina Poisson + logística via CES",
        },
        "validation_season": season,
        "n_matches": len(rows),
        "lgn_warning": warning,
        "accuracy_bootstrap_poisson": acc_ci_p,
        "accuracy_bootstrap_ensemble": acc_ci_e,
        "calibration_bins_poisson": cal_bins_p,
        "calibration_bins_ensemble": cal_bins_e,
        "calibration_chart": {
            "poisson": _chart_points(cal_bins_p),
            "ensemble_dixit": _chart_points(cal_bins_e),
            "perfect_calibration": [
                {"confidence_pct": 0, "observed_pct": 0},
                {"confidence_pct": 100, "observed_pct": 100},
            ],
        },
        "ensemble_holdout": {
            "accuracy": collab_metrics.accuracy,
            "brier": collab_metrics.brier_score,
            "poisson_weight": collab.poisson_weight,
            "logistic_weight": collab.logistic_weight,
            "dixit_sigma": settings.dixit_sigma,
        },
        "platt_calibration": platt_section,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibração LGN — Copa (holdout)")
    parser.add_argument("--validation-season", type=int, default=settings.wc_validation_season)
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "wc_calibration_report.json",
    )
    args = parser.parse_args()

    report = run_calibration_study(args.validation_season)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório: {args.output}")
    if report.get("lgn_warning"):
        print(report["lgn_warning"])
    for label, key in [("Poisson", "accuracy_bootstrap_poisson"), ("Ensemble", "accuracy_bootstrap_ensemble")]:
        ab = report[key]
        if ab.get("mean") is not None:
            print(
                f"Acurácia {label}: {ab['mean']:.3f} "
                f"IC95% [{ab['ci_low']:.3f}, {ab['ci_high']:.3f}]"
            )
    eh = report["ensemble_holdout"]
    print(
        f"Ensemble (Dixit): acc={eh['accuracy']:.3f} brier={eh['brier']:.4f} "
        f"w_poisson={eh['poisson_weight']:.2f}"
    )
    pc = report["platt_calibration"]
    print(
        f"Platt calibração: ECE {pc['ece_before']:.4f} → {pc['ece_after']:.4f} "
        f"({pc['ece_reduction_pct']:+.1f}%) | "
        f"Brier {pc['brier_before']:.4f} → {pc['brier_after']:.4f}"
    )


if __name__ == "__main__":
    main()
