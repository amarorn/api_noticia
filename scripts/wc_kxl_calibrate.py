#!/usr/bin/env python3
"""Calibração rápida: ensemble histórico vs blend KXL no holdout 2022."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingest.fixtures.world_cup import load_wc_fixtures  # noqa: E402
from models.wc_predictor import WcPredictor  # noqa: E402
from pipelines.wc_baselines import blend_with_baseline, load_team_baselines, resolve_baseline_team  # noqa: E402
from pipelines.wc_stats import build_match_features  # noqa: E402


def _brier(probs: dict[str, float], label: str) -> float:
    one_hot = {"1": 0.0, "X": 0.0, "2": 0.0}
    one_hot[label] = 1.0
    return sum((probs[k] - one_hot[k]) ** 2 for k in one_hot)


def _accuracy(probs: dict[str, float], label: str) -> float:
    pred = max(probs, key=probs.get)
    return 1.0 if pred == label else 0.0


def evaluate(season: int = 2022, blend_weight: float = 0.25) -> dict:
    df = load_wc_fixtures()
    subset = df[(df["season"] == season) & df["label"].notna()].copy()
    predictor = WcPredictor(df)
    baselines = load_team_baselines()

    rows = []
    for _, row in subset.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        if resolve_baseline_team(home) not in baselines or resolve_baseline_team(away) not in baselines:
            continue
        kickoff = row.get("date")
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
            predictor.fixtures,
            home,
            away,
            features,
            before_date=before,
        )
        logistic = predictor.logistic.predict_match(
            predictor.fixtures,
            home,
            away,
            phase=str(row.get("phase") or "group"),
            is_neutral=True,
            before_date=before,
        )
        pw = predictor.collaborative.dixon_coles_weight
        lw = predictor.collaborative.logistic_weight
        ph = pw * poisson.prob_home + lw * logistic.prob_home
        pd = pw * poisson.prob_draw + lw * logistic.prob_draw
        pa = pw * poisson.prob_away + lw * logistic.prob_away
        total = ph + pd + pa
        ensemble = {"1": ph / total, "X": pd / total, "2": pa / total}

        bh, bd, ba, _ = blend_with_baseline(ph / total, pd / total, pa / total, home, away, weight=blend_weight)
        blended = {"1": bh, "X": bd, "2": ba}

        label = str(row["label"])
        rows.append(
            {
                "home": home,
                "away": away,
                "label": label,
                "ensemble_brier": _brier(ensemble, label),
                "blend_brier": _brier(blended, label),
                "ensemble_ok": _accuracy(ensemble, label),
                "blend_ok": _accuracy(blended, label),
            }
        )

    if not rows:
        return {"season": season, "matches": 0, "message": "Nenhum jogo com baselines KXL para ambos os times"}

    n = len(rows)
    return {
        "season": season,
        "matches_evaluated": n,
        "blend_weight": blend_weight,
        "ensemble": {
            "accuracy": round(sum(r["ensemble_ok"] for r in rows) / n, 4),
            "brier_mean": round(sum(r["ensemble_brier"] for r in rows) / n, 6),
        },
        "ensemble_plus_kxl_blend": {
            "accuracy": round(sum(r["blend_ok"] for r in rows) / n, 4),
            "brier_mean": round(sum(r["blend_brier"] for r in rows) / n, 6),
        },
        "delta_brier_blend_minus_ensemble": round(
            sum(r["blend_brier"] - r["ensemble_brier"] for r in rows) / n,
            6,
        ),
        "target_meta_pdf": "erro marginal ±5–8% vs holdout (referência documento KXL)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2022)
    parser.add_argument("--blend-weight", type=float, default=0.25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = evaluate(season=args.season, blend_weight=args.blend_weight)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
