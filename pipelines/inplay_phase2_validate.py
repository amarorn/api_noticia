"""Validação Fase 2: coeficientes MLE vs constantes Fase 1.

CLI: validate-inplay-phase2 [--eval-season 2022]
"""
from __future__ import annotations

import argparse
import json

from pipelines.wc_inplay_walkforward import evaluate_inplay


def run_phase2_validation(
    *,
    eval_season: int = 2022,
    n_simulations: int = 2000,
    verbose: bool = True,
) -> dict:
    """Compara walk-forward com momentum calibrado vs constantes default."""
    report: dict = {"eval_season": eval_season, "variants": {}}

    variants = (
        ("fase1_constantes", False),
        ("fase2_calibrado", True),
    )

    for name, calibrated in variants:
        result = evaluate_inplay(
            eval_season=eval_season,
            n_simulations=n_simulations,
            use_momentum=True,
            use_nhpp=True,
            use_calibrated_coefficients=calibrated,
            verbose=False,
        )
        entry = {
            "brier_overall": result.brier_overall,
            "brier_by_minute": result.brier_by_minute,
            "n_samples": result.n_samples,
            "n_games": result.n_games,
        }
        report["variants"][name] = entry
        if verbose:
            print(
                f"  {name:22s} Brier={result.brier_overall:.5f} "
                f"(min15={result.brier_by_minute.get(15, 0):.5f}, "
                f"min75={result.brier_by_minute.get(75, 0):.5f})"
            )

    base = report["variants"]["fase1_constantes"]["brier_overall"]
    cal = report["variants"]["fase2_calibrado"]["brier_overall"]
    report["fase2_gain"] = round(base - cal, 6)

    b15_base = report["variants"]["fase1_constantes"]["brier_by_minute"].get(15, 0)
    b15_cal = report["variants"]["fase2_calibrado"]["brier_by_minute"].get(15, 0)
    b75_base = report["variants"]["fase1_constantes"]["brier_by_minute"].get(75, 0)
    b75_cal = report["variants"]["fase2_calibrado"]["brier_by_minute"].get(75, 0)
    report["gain_min15"] = round(b15_base - b15_cal, 6)
    report["gain_min75"] = round(b75_base - b75_cal, 6)

    if verbose:
        print(f"\n  Ganho Fase 2 vs Fase 1: {report['fase2_gain']:+.5f} Brier")
        print(f"  Ganho min 15: {report['gain_min15']:+.5f}")
        print(f"  Ganho min 75: {report['gain_min75']:+.5f}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação Fase 2 in-play (MLE)")
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--n-simulations", type=int, default=2000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    verbose = not args.json
    if verbose:
        print("=== VALIDAÇÃO FASE 2 IN-PLAY ===")

    report = run_phase2_validation(
        eval_season=args.eval_season,
        n_simulations=args.n_simulations,
        verbose=verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
