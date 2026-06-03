"""
Validação walk-forward por edição da Copa (Sprint 3).
Treina só com temporadas anteriores à edição avaliada.
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from models.dixon_coles_wc import DixonColesWcModel
from models.logistic_wc import WcLogisticModel
from models.wc_collaborative import CollaborativeWcModel
from pipelines.wc_stats import build_match_features


def _brier(y_true: list[str], probs: list[dict[str, float]]) -> float:
    labels = ("1", "X", "2")
    total = 0.0
    for y, p in zip(y_true, probs, strict=True):
        for label in labels:
            target = 1.0 if y == label else 0.0
            total += (p[label] - target) ** 2
    return total / (len(y_true) * len(labels)) if y_true else 0.0


def _eval_season(
    fixtures: pd.DataFrame,
    eval_season: int,
    min_prior_matches: int = 80,
) -> dict | None:
    train = fixtures[fixtures["season"] < eval_season]
    test = fixtures[fixtures["season"] == eval_season]
    if len(train) < min_prior_matches or test.empty:
        return None

    logistic = WcLogisticModel()
    logistic.fit(train, holdout_season=None)
    dixon = DixonColesWcModel()
    dixon.fit(fixtures, holdout_season=eval_season)
    collab = CollaborativeWcModel(dixon_coles=dixon)
    collab.fit(fixtures, validation_season=eval_season, logistic_model=logistic)

    rows: list[dict] = []
    y_true: list[str] = []
    probs: list[dict[str, float]] = []

    for _, row in test.sort_values("match_date").iterrows():
        before = row["match_date"]
        history = fixtures[pd.to_datetime(fixtures["match_date"], utc=True) < pd.to_datetime(before, utc=True)]
        if history.empty:
            continue
        phase = row.get("phase", "group")
        is_neutral = bool(row.get("is_neutral", True))
        features = build_match_features(
            history,
            row["home_team"],
            row["away_team"],
            before_date=before,
            phase=phase,
            is_neutral=is_neutral,
        )
        poisson = dixon.predict(
            history,
            row["home_team"],
            row["away_team"],
            features=features,
            before_date=before,
        )
        log_pred = logistic.predict_match(
            history,
            row["home_team"],
            row["away_team"],
            phase=phase,
            is_neutral=is_neutral,
        )
        dw = collab.dixon_coles_weight
        lw = collab.logistic_weight
        p = {
            "1": dw * poisson.prob_home + lw * log_pred.prob_home,
            "X": dw * poisson.prob_draw + lw * log_pred.prob_draw,
            "2": dw * poisson.prob_away + lw * log_pred.prob_away,
        }
        total = sum(p.values())
        p = {k: v / total for k, v in p.items()}
        pred = max(p, key=p.get)
        y_true.append(row["label"])
        probs.append(p)
        rows.append(
            {
                "home": row["home_team"],
                "away": row["away_team"],
                "label": row["label"],
                "prediction": pred,
                "correct": pred == row["label"],
            }
        )

    if not y_true:
        return None

    correct = sum(1 for r in rows if r["correct"])
    return {
        "eval_season": eval_season,
        "train_seasons": sorted(int(s) for s in train["season"].unique()),
        "train_matches": int(len(train)),
        "eval_matches": len(y_true),
        "accuracy": correct / len(y_true),
        "brier": _brier(y_true, probs),
        "ensemble_weights": {
            "dixon_coles": round(collab.dixon_coles_weight, 3),
            "logistic": round(collab.logistic_weight, 3),
        },
    }


def run_walkforward(
    *,
    min_eval_season: int = 1970,
    min_prior_matches: int = 80,
    max_editions: int | None = 12,
) -> dict:
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Sem fixtures WC. Execute: import-world-cup")

    seasons = sorted(int(s) for s in fixtures["season"].unique() if int(s) >= min_eval_season)
    if max_editions:
        seasons = seasons[-max_editions:]

    editions: list[dict] = []
    for season in seasons:
        row = _eval_season(fixtures, season, min_prior_matches=min_prior_matches)
        if row:
            editions.append(row)

    briers = [e["brier"] for e in editions]
    accs = [e["accuracy"] for e in editions]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "min_eval_season": min_eval_season,
        "min_prior_matches": min_prior_matches,
        "editions_evaluated": len(editions),
        "summary": {
            "mean_accuracy": float(np.mean(accs)) if accs else 0.0,
            "mean_brier": float(np.mean(briers)) if briers else 0.0,
            "worst_brier_season": editions[int(np.argmax(briers))]["eval_season"] if briers else None,
            "best_brier_season": editions[int(np.argmin(briers))]["eval_season"] if briers else None,
        },
        "editions": editions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward por edição da Copa")
    parser.add_argument("--min-season", type=int, default=1970)
    parser.add_argument("--min-train-matches", type=int, default=80)
    parser.add_argument("--max-editions", type=int, default=12)
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "wc_walkforward_report.json",
    )
    args = parser.parse_args()

    report = run_walkforward(
        min_eval_season=args.min_season,
        min_prior_matches=args.min_train_matches,
        max_editions=args.max_editions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    s = report["summary"]
    print(f"Relatório: {args.output}")
    print(
        f"Edições: {report['editions_evaluated']} | "
        f"acc média={s['mean_accuracy']:.3f} brier média={s['mean_brier']:.4f}"
    )
    if s.get("best_brier_season"):
        print(f"Melhor Brier: {s['best_brier_season']} | Pior: {s['worst_brier_season']}")


if __name__ == "__main__":
    main()
