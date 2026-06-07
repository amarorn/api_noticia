#!/usr/bin/env python3
"""Validação walk-forward em lote por edição da Copa."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from ingest.fixtures.world_cup import edition_label, load_wc_fixtures
from models.wc_artifact import load_artifact
from pipelines.wc_validate import list_edition_matches, validate_historical_match


def brier(probs: dict[str, float], label: str) -> float:
    target = {"1": 0.0, "X": 0.0, "2": 0.0}
    target[label] = 1.0
    return sum((probs[k] - target[k]) ** 2 for k in "1X2")


def log_loss(probs: dict[str, float], label: str, eps: float = 1e-12) -> float:
    return -math.log(max(probs.get(label, eps), eps))


def validate_edition(predictor, fixtures, season: int) -> dict:
    matches = list_edition_matches(fixtures, season)
    rows: list[dict] = []
    by_phase: dict[str, dict] = defaultdict(
        lambda: {"n": 0, "correct": 0, "brier": 0.0, "log_loss": 0.0}
    )
    pred_dist: Counter[str] = Counter()
    actual_dist: Counter[str] = Counter()

    for m in matches:
        r = validate_historical_match(
            predictor,
            fixtures,
            season,
            match_id=m["match_id"],
        )
        actual = r["match"]["actual_result"]
        pred = r["prediction"]
        probs = {"1": r["prob_home"], "X": r["prob_draw"], "2": r["prob_away"]}
        phase = r["match"]["phase"]
        br = brier(probs, actual)
        ll = log_loss(probs, actual)

        rows.append(
            {
                "home": m["home_team"],
                "away": m["away_team"],
                "phase": phase,
                "actual": actual,
                "pred": pred,
                "correct": pred == actual,
                "brier": br,
                "log_loss": ll,
                "confidence": r["confidence"],
            }
        )
        pred_dist[pred] += 1
        actual_dist[actual] += 1
        by_phase[phase]["n"] += 1
        by_phase[phase]["correct"] += int(pred == actual)
        by_phase[phase]["brier"] += br
        by_phase[phase]["log_loss"] += ll

    n = len(rows)
    return {
        "label": edition_label(season),
        "matches": n,
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "brier": round(sum(r["brier"] for r in rows) / n, 4),
        "log_loss": round(sum(r["log_loss"] for r in rows) / n, 4),
        "baseline_always_home": round(sum(1 for r in rows if r["actual"] == "1") / n, 4),
        "baseline_majority_class": round(max(actual_dist.values()) / n, 4),
        "pred_distribution": dict(pred_dist),
        "actual_distribution": dict(actual_dist),
        "by_phase": {
            phase: {
                "matches": stats["n"],
                "accuracy": round(stats["correct"] / stats["n"], 4),
                "brier": round(stats["brier"] / stats["n"], 4),
            }
            for phase, stats in sorted(by_phase.items())
        },
        "wrong_high_confidence": sorted(
            [
                {
                    "match": f"{r['home']} x {r['away']}",
                    "actual": r["actual"],
                    "pred": r["pred"],
                    "confidence": round(r["confidence"], 3),
                }
                for r in rows
                if not r["correct"]
            ],
            key=lambda item: -item["confidence"],
        )[:5],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=[2018, 2022])
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/lake/artifacts/wc_predictor/batch_validation.json"),
    )
    args = parser.parse_args()

    predictor = load_artifact()
    if predictor is None:
        raise SystemExit("Artefato WC inválido — rode: train-wc --force")

    fixtures = load_wc_fixtures()
    manifest_path = Path("data/lake/artifacts/wc_predictor/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    report = {
        "artifact_created_at": manifest.get("created_at"),
        "ensemble_weights": manifest.get("ensemble_weights"),
        "holdout_training": manifest.get("training_metrics", {}).get("holdout_accuracy"),
        "fixture_rows": len(fixtures),
        "editions": {},
    }

    for season in args.seasons:
        print(f"Validando {season}…", flush=True)
        report["editions"][str(season)] = validate_edition(predictor, fixtures, season)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
