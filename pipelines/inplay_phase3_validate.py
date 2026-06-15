"""Validação Fase 3: ensemble Hawkes + GBM vs Poisson Fase 2.

CLI: validate-inplay-phase3 [--eval-season 2022]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from pipelines.wc_inplay_walkforward import evaluate_inplay


@dataclass(frozen=True)
class Phase3Variant:
    name: str
    use_ensemble: bool
    use_hawkes: bool | None = None
    use_gbm: bool | None = None


PHASE3_VARIANTS = (
    Phase3Variant("fase2_poisson", use_ensemble=False),
    Phase3Variant("fase3_hawkes_only", use_ensemble=True, use_hawkes=True, use_gbm=False),
    Phase3Variant("fase3_gbm_only", use_ensemble=True, use_hawkes=False, use_gbm=True),
    Phase3Variant("fase3_ensemble_full", use_ensemble=True, use_hawkes=True, use_gbm=True),
)


def run_phase3_validation(
    *,
    eval_season: int = 2022,
    n_simulations: int = 1500,
    verbose: bool = True,
) -> dict:
    """Compara walk-forward Poisson Fase 2 vs variantes do ensemble Fase 3."""
    report: dict = {"eval_season": eval_season, "variants": {}}

    for variant in PHASE3_VARIANTS:
        result = evaluate_inplay(
            eval_season=eval_season,
            n_simulations=n_simulations,
            use_momentum=True,
            use_nhpp=True,
            use_calibrated_coefficients=True,
            use_ensemble=variant.use_ensemble,
            use_ensemble_hawkes=variant.use_hawkes,
            use_ensemble_gbm=variant.use_gbm,
            verbose=False,
        )
        entry = {
            "brier_overall": result.brier_overall,
            "brier_by_minute": result.brier_by_minute,
            "n_samples": result.n_samples,
            "elapsed_seconds": result.elapsed_seconds,
        }
        report["variants"][variant.name] = entry
        if verbose:
            b60 = result.brier_by_minute.get(60, 0)
            b75 = result.brier_by_minute.get(75, 0)
            print(
                f"  {variant.name:22s} Brier={result.brier_overall:.5f} "
                f"(min60={b60:.5f}, min75={b75:.5f}, {result.elapsed_seconds:.0f}s)"
            )

    base = report["variants"]["fase2_poisson"]["brier_overall"]
    full = report["variants"]["fase3_ensemble_full"]["brier_overall"]
    gbm = report["variants"]["fase3_gbm_only"]["brier_overall"]
    hawkes = report["variants"]["fase3_hawkes_only"]["brier_overall"]

    report["gain_ensemble_full"] = round(base - full, 6)
    report["gain_gbm_only"] = round(base - gbm, 6)
    report["gain_hawkes_only"] = round(base - hawkes, 6)

    if verbose:
        print(f"\n  Ganho ensemble completo: {report['gain_ensemble_full']:+.5f}")
        print(f"  Ganho só GBM:            {report['gain_gbm_only']:+.5f}")
        print(f"  Ganho só Hawkes:         {report['gain_hawkes_only']:+.5f}")
        if report["gain_ensemble_full"] >= 0.005:
            print("  ✅ Alvo Fase 3 atingido (≥ 0.005 Brier)")
        else:
            print("  ⚠️  Shadow mode recomendado (INPLAY_ENSEMBLE_SHADOW_MODE=true)")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação Fase 3 in-play (ensemble)")
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--n-simulations", type=int, default=1500)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    verbose = not args.json
    if verbose:
        print("=== VALIDAÇÃO FASE 3 IN-PLAY ===")

    report = run_phase3_validation(
        eval_season=args.eval_season,
        n_simulations=args.n_simulations,
        verbose=verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
