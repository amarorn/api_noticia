"""Calibra peso do blend KXL no holdout (Sprint 4)."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from models.wc_predictor import WcPredictor
from pipelines.wc_baselines import blend_with_baseline, load_team_baselines, resolve_baseline_team
from pipelines.wc_hyperparams import HYPERPARAMS_PATH, get_wc_hyperparams, load_hyperparams_file
from pipelines.wc_stats import build_match_features


def _brier(probs: dict[str, float], label: str) -> float:
    one_hot = {"1": 0.0, "X": 0.0, "2": 0.0}
    one_hot[label] = 1.0
    return sum((probs[k] - one_hot[k]) ** 2 for k in one_hot)


def tune_kxl_blend(
    season: int = 2022,
    weights: tuple[float, ...] = (0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4),
) -> dict:
    df = load_wc_fixtures()
    subset = df[(df["season"] == season) & df["label"].notna()].copy()
    predictor = WcPredictor(df)
    baselines = load_team_baselines()

    eligible = []
    for _, row in subset.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        if resolve_baseline_team(home) not in baselines or resolve_baseline_team(away) not in baselines:
            continue
        eligible.append(row)

    if not eligible:
        return {"season": season, "matches": 0, "message": "Sem jogos com baselines KXL"}

    grid_results: list[dict] = []
    for weight in weights:
        briers: list[float] = []
        for row in eligible:
            home = str(row["home_team"])
            away = str(row["away_team"])
            kickoff = row.get("match_date")
            before = kickoff if kickoff is not None else datetime(2022, 11, 20, tzinfo=timezone.utc)
            features = build_match_features(
                predictor.fixtures,
                home,
                away,
                before_date=before,
                phase=str(row.get("phase") or "group"),
                is_neutral=True,
            )
            poisson = predictor.dixon_coles.predict(
                predictor.fixtures, home, away, features, before_date=before
            )
            logistic = predictor.logistic.predict_match(
                predictor.fixtures, home, away, before_date=before
            )
            pw = predictor.collaborative.dixon_coles_weight
            lw = predictor.collaborative.logistic_weight
            ph = pw * poisson.prob_home + lw * logistic.prob_home
            pd_ = pw * poisson.prob_draw + lw * logistic.prob_draw
            pa = pw * poisson.prob_away + lw * logistic.prob_away
            total = ph + pd_ + pa
            bh, bd, ba, _ = blend_with_baseline(
                ph / total, pd_ / total, pa / total, home, away, weight=weight
            )
            briers.append(_brier({"1": bh, "X": bd, "2": ba}, str(row["label"])))

        grid_results.append(
            {
                "blend_weight": weight,
                "brier_mean": round(sum(briers) / len(briers), 6),
                "matches": len(briers),
            }
        )

    best = min(grid_results, key=lambda r: r["brier_mean"])
    current = get_wc_hyperparams().kxl_blend_weight
    return {
        "season": season,
        "matches_evaluated": len(eligible),
        "current_blend_weight": current,
        "best_blend_weight": best["blend_weight"],
        "best_brier_mean": best["brier_mean"],
        "grid": grid_results,
        "recommend_apply": best["blend_weight"] != current,
    }


def apply_best_weight(weight: float) -> None:
    hp = load_hyperparams_file() or get_wc_hyperparams()
    payload = asdict(hp)
    payload["kxl_blend_weight"] = weight
    HYPERPARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    HYPERPARAMS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibra peso KXL no holdout")
    parser.add_argument("--season", type=int, default=2022)
    parser.add_argument("--apply", action="store_true", help="Grava melhor peso em hyperparams.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "wc_kxl_blend_report.json",
    )
    args = parser.parse_args()
    report = tune_kxl_blend(season=args.season)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Relatório: {args.output}")
    if report.get("matches_evaluated"):
        print(
            f"Melhor peso: {report['best_blend_weight']} "
            f"(Brier {report['best_brier_mean']}, atual {report['current_blend_weight']})"
        )
        if args.apply and report.get("recommend_apply"):
            apply_best_weight(report["best_blend_weight"])
            print("hyperparams.json atualizado")


if __name__ == "__main__":
    main()
