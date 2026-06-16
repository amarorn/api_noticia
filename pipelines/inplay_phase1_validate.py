"""Validação A/B da Fase 1 in-play (NHPP + momentum + flags).

Compara Brier walk-forward entre combinações de feature flags.
Shrinkage de mercado não entra no walk-forward (sem odds históricas).

CLI: validate-inplay-phase1 [--eval-season 2022] [--verbose]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from pipelines.wc_inplay_walkforward import evaluate_inplay


@dataclass(frozen=True)
class Phase1Variant:
    name: str
    use_nhpp: bool
    use_momentum: bool


PHASE1_VARIANTS = (
    Phase1Variant("baseline_homogeneo_sem_momentum", use_nhpp=False, use_momentum=False),
    Phase1Variant("somente_nhpp", use_nhpp=True, use_momentum=False),
    Phase1Variant("somente_momentum", use_nhpp=False, use_momentum=True),
    Phase1Variant("fase1_completa", use_nhpp=True, use_momentum=True),
)


def run_phase1_ablation(
    *,
    eval_season: int = 2022,
    n_simulations: int = 2000,
    verbose: bool = True,
) -> dict:
    """Roda walk-forward para cada variante da Fase 1."""
    report: dict = {"eval_season": eval_season, "variants": {}}
    baseline_brier: float | None = None

    for variant in PHASE1_VARIANTS:
        result = evaluate_inplay(
            eval_season=eval_season,
            n_simulations=n_simulations,
            use_momentum=variant.use_momentum,
            use_nhpp=variant.use_nhpp,
            verbose=False,
        )
        entry = {
            "brier_overall": result.brier_overall,
            "brier_by_minute": result.brier_by_minute,
            "n_samples": result.n_samples,
            "n_games": result.n_games,
            "elapsed_seconds": result.elapsed_seconds,
        }
        if baseline_brier is None:
            baseline_brier = result.brier_overall
            entry["delta_vs_baseline"] = 0.0
        else:
            entry["delta_vs_baseline"] = round(result.brier_overall - baseline_brier, 6)

        report["variants"][variant.name] = entry

        if verbose:
            delta = entry["delta_vs_baseline"]
            sign = "+" if delta > 0 else ""
            print(
                f"  {variant.name:32s} Brier={result.brier_overall:.5f} "
                f"({sign}{delta:.5f} vs baseline, n={result.n_samples})"
            )

    full = report["variants"].get("fase1_completa", {})
    base = report["variants"].get("baseline_homogeneo_sem_momentum", {})
    if full and base:
        report["fase1_gain"] = round(
            base.get("brier_overall", 0) - full.get("brier_overall", 0), 6
        )
        if verbose:
            print(f"\n  Ganho Fase 1 completa vs baseline: {report['fase1_gain']:+.5f} Brier")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validação A/B Fase 1 in-play")
    parser.add_argument("--eval-season", type=int, default=2022)
    parser.add_argument("--n-simulations", type=int, default=2000)
    parser.add_argument("--verbose", "-v", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    verbose = not args.json and args.verbose
    if verbose:
        print("=== VALIDAÇÃO FASE 1 IN-PLAY ===")

    report = run_phase1_ablation(
        eval_season=args.eval_season,
        n_simulations=args.n_simulations,
        verbose=verbose,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
