"""
Busca em grade de hiperparâmetros no holdout (padrão: Copa 2022).
Salva o melhor conjunto em data/wc/hyperparams.json.
"""
from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from config import settings
from ingest.fixtures.world_cup import load_wc_fixtures
from models.dixon_coles_wc import DixonColesWcModel
from models.logistic_wc import WcLogisticModel
from models.wc_collaborative import CollaborativeWcModel
from pipelines.wc_baselines import blend_with_baseline, load_team_baselines, resolve_baseline_team
from pipelines.wc_hyperparams import (
    WcHyperParams,
    save_hyperparams,
    set_active_hyperparams,
)
from pipelines.wc_stats import build_match_features


def _brier_multiclass(rows: list[dict]) -> float:
    labels = ("1", "X", "2")
    total = 0.0
    for row in rows:
        y = row["label"]
        probs = row["probs"]
        for label in labels:
            target = 1.0 if y == label else 0.0
            total += (probs[label] - target) ** 2
    return total / (len(rows) * len(labels)) if rows else 1.0


def _apply_draw_floor(probs: dict[str, float], floor: float) -> dict[str, float]:
    if floor <= 0:
        return probs
    px = max(probs["X"], floor)
    rem = 1.0 - px
    scale = rem / max(probs["1"] + probs["2"], 1e-9)
    return {"1": probs["1"] * scale, "X": px, "2": probs["2"] * scale}


def evaluate_hyperparams(
    fixtures: pd.DataFrame,
    hp: WcHyperParams,
    validation_season: int,
) -> dict:
    set_active_hyperparams(hp)
    try:
        logistic = WcLogisticModel()
        logistic.fit(fixtures, holdout_season=None)
        dixon = DixonColesWcModel()
        dixon.fit(fixtures, holdout_season=validation_season)
        collab = CollaborativeWcModel(dixon_coles=dixon)
        collab.fit(fixtures, validation_season=validation_season, logistic_model=logistic)

        valid_df = fixtures[fixtures["season"] == validation_season]
        baselines = load_team_baselines()
        scored: list[dict] = []
        correct = 0

        for _, row in valid_df.iterrows():
            before = row["match_date"]
            history = fixtures[fixtures["match_date"] < before]
            if history.empty:
                continue
            phase = row.get("phase", "group")
            is_neutral = bool(row.get("is_neutral", True))
            home, away = row["home_team"], row["away_team"]
            features = build_match_features(
                history, home, away, before_date=before, phase=phase, is_neutral=is_neutral
            )
            poisson = dixon.predict(history, home, away, features=features, before_date=before)
            log_pred = logistic.predict_match(
                history, home, away, phase=phase, is_neutral=is_neutral, before_date=before
            )
            dw, lw = collab.dixon_coles_weight, collab.logistic_weight
            probs = {
                "1": dw * poisson.prob_home + lw * log_pred.prob_home,
                "X": dw * poisson.prob_draw + lw * log_pred.prob_draw,
                "2": dw * poisson.prob_away + lw * log_pred.prob_away,
            }
            total = sum(probs.values())
            probs = {k: v / total for k, v in probs.items()}
            probs = _apply_draw_floor(probs, hp.draw_prob_floor)

            if (
                resolve_baseline_team(home) in baselines
                and resolve_baseline_team(away) in baselines
            ):
                ph, pd, pa, _ = blend_with_baseline(
                    probs["1"], probs["X"], probs["2"], home, away, weight=hp.kxl_blend_weight
                )
                probs = {"1": ph, "X": pd, "2": pa}

            pred = max(probs, key=probs.get)
            if pred == row["label"]:
                correct += 1
            scored.append({"label": row["label"], "probs": probs})

        brier = _brier_multiclass(scored)
        dist = {"1": 0, "X": 0, "2": 0}
        for s in scored:
            dist[max(s["probs"], key=s["probs"].get)] += 1

        return {
            "brier": brier,
            "accuracy": correct / len(scored) if scored else 0.0,
            "n": len(scored),
            "pred_distribution": dist,
            "ensemble_weights": {
                "dixon_coles": collab.dixon_coles_weight,
                "logistic": collab.logistic_weight,
            },
        }
    finally:
        set_active_hyperparams(None)


def _grid(full: bool = False) -> list[WcHyperParams]:
    base = WcHyperParams()
    if full:
        space = itertools.product(
            [20.0, 30.0, 40.0],
            [0.0, 0.04, 0.08],
            [0.5, 0.85, 1.2],
            ["balanced", None],
            [0.15, 0.20, 0.25],
            [0.16, 0.18, 0.20, 0.22],
        )
    else:
        space = itertools.product(
            [25.0, 30.0, 35.0],
            [0.03, 0.05, 0.07],
            [0.7, 0.85, 1.0],
            ["balanced"],
            [0.18, 0.20, 0.22],
            [0.17, 0.19, 0.21],
        )
    combos = space
    out: list[WcHyperParams] = []
    for elo_adv, home_neu, c, cw, kxl, floor in combos:
        cw_val = cw if cw != "none" else None
        out.append(
            replace(
                base,
                elo_home_adv=elo_adv,
                home_adv_goals_neutral=home_neu,
                logistic_c=c,
                logistic_class_weight=cw_val,
                kxl_blend_weight=kxl,
                draw_prob_floor=floor,
            )
        )
    return out


def _fast_postprocess_tune(
    fixtures: pd.DataFrame,
    validation_season: int,
    base_hp: WcHyperParams,
) -> tuple[WcHyperParams, dict]:
    """Calibra KXL e piso de empate sem retreinar (rápido)."""
    set_active_hyperparams(base_hp)
    try:
        logistic = WcLogisticModel()
        logistic.fit(fixtures, holdout_season=None)
        dixon = DixonColesWcModel()
        dixon.fit(fixtures, holdout_season=validation_season)
        collab = CollaborativeWcModel(dixon_coles=dixon)
        collab.fit(fixtures, validation_season=validation_season, logistic_model=logistic)

        valid_df = fixtures[fixtures["season"] == validation_season]
        baselines = load_team_baselines()
        base_rows: list[dict] = []

        for _, row in valid_df.iterrows():
            before = row["match_date"]
            history = fixtures[fixtures["match_date"] < before]
            if history.empty:
                continue
            phase = row.get("phase", "group")
            is_neutral = bool(row.get("is_neutral", True))
            home, away = row["home_team"], row["away_team"]
            features = build_match_features(
                history, home, away, before_date=before, phase=phase, is_neutral=is_neutral
            )
            poisson = dixon.predict(history, home, away, features=features, before_date=before)
            log_pred = logistic.predict_match(
                history, home, away, phase=phase, is_neutral=is_neutral, before_date=before
            )
            dw, lw = collab.dixon_coles_weight, collab.logistic_weight
            probs = {
                "1": dw * poisson.prob_home + lw * log_pred.prob_home,
                "X": dw * poisson.prob_draw + lw * log_pred.prob_draw,
                "2": dw * poisson.prob_away + lw * log_pred.prob_away,
            }
            total = sum(probs.values())
            base_rows.append(
                {
                    "label": row["label"],
                    "probs": {k: v / total for k, v in probs.items()},
                    "home": home,
                    "away": away,
                }
            )

        best_hp = base_hp
        best_metrics: dict | None = None
        for kxl in (0.15, 0.18, 0.20, 0.22, 0.25):
            for floor in (0.16, 0.17, 0.18, 0.19, 0.20, 0.21):
                hp = replace(base_hp, kxl_blend_weight=kxl, draw_prob_floor=floor)
                scored: list[dict] = []
                correct = 0
                for item in base_rows:
                    probs = _apply_draw_floor(item["probs"], floor)
                    if (
                        resolve_baseline_team(item["home"]) in baselines
                        and resolve_baseline_team(item["away"]) in baselines
                    ):
                        ph, pd, pa, _ = blend_with_baseline(
                            probs["1"],
                            probs["X"],
                            probs["2"],
                            item["home"],
                            item["away"],
                            weight=kxl,
                        )
                        probs = {"1": ph, "X": pd, "2": pa}
                    pred = max(probs, key=probs.get)
                    if pred == item["label"]:
                        correct += 1
                    scored.append({"label": item["label"], "probs": probs})
                metrics = {
                    "brier": _brier_multiclass(scored),
                    "accuracy": correct / len(scored) if scored else 0.0,
                    "n": len(scored),
                    "pred_distribution": {
                        "1": sum(1 for s in scored if max(s["probs"], key=s["probs"].get) == "1"),
                        "X": sum(1 for s in scored if max(s["probs"], key=s["probs"].get) == "X"),
                        "2": sum(1 for s in scored if max(s["probs"], key=s["probs"].get) == "2"),
                    },
                    "ensemble_weights": {
                        "dixon_coles": collab.dixon_coles_weight,
                        "logistic": collab.logistic_weight,
                    },
                }
                if best_metrics is None or metrics["brier"] < best_metrics["brier"]:
                    best_hp = hp
                    best_metrics = metrics
        assert best_metrics is not None
        return best_hp, best_metrics
    finally:
        set_active_hyperparams(None)


def run_tune(
    validation_season: int = 2022,
    max_candidates: int | None = None,
    full_grid: bool = False,
    fast: bool = True,
) -> dict:
    fixtures = load_wc_fixtures()
    if fixtures.empty:
        raise ValueError("Sem fixtures. Execute: import-world-cup")

    if fast:
        base = WcHyperParams()
        structural_grid = list(
            itertools.product(
                [20.0, 24.0, 28.0, 32.0],
                [25.0, 30.0, 35.0],
                [0.03, 0.04, 0.05],
                [0.7, 0.85, 1.0],
            )
        )
        if max_candidates and max_candidates < len(structural_grid):
            structural_grid = structural_grid[:max_candidates]
        best_hp: WcHyperParams | None = None
        best_metrics: dict | None = None
        print(f"Fase 1: {len(structural_grid)} combinações estruturais...")
        for i, (elo_k, elo_adv, home_neu, c) in enumerate(structural_grid):
            hp = replace(
                base,
                elo_k=elo_k,
                elo_home_adv=elo_adv,
                home_adv_goals_neutral=home_neu,
                logistic_c=c,
                logistic_class_weight="balanced",
            )
            metrics = evaluate_hyperparams(fixtures, hp, validation_season)
            if best_metrics is None or metrics["brier"] < best_metrics["brier"]:
                best_hp = hp
                best_metrics = metrics
            print(
                f"  [{i + 1}/{len(structural_grid)}] brier={metrics['brier']:.4f} "
                f"K={elo_k} elo={elo_adv} home={home_neu} C={c}"
            )
        assert best_hp is not None and best_metrics is not None
        print("Fase 2: KXL + piso de empate (rápido)...")
        best_hp, post_metrics = _fast_postprocess_tune(fixtures, validation_season, best_hp)
        best_metrics = {**best_metrics, **post_metrics, "phase2": True}
    else:
        grid = _grid(full=full_grid)
        if max_candidates:
            grid = grid[:max_candidates]
        best_hp = None
        best_metrics = None
        for i, hp in enumerate(grid):
            metrics = evaluate_hyperparams(fixtures, hp, validation_season)
            if best_metrics is None or metrics["brier"] < best_metrics["brier"]:
                best_hp = hp
                best_metrics = metrics
            if (i + 1) % 20 == 0:
                print(
                    f"  {i + 1}/{len(grid)} candidatos... "
                    f"melhor brier={best_metrics['brier']:.4f}"
                )

    assert best_hp is not None and best_metrics is not None
    meta = {
        "tuned_at": datetime.now(UTC).isoformat(),
        "validation_season": validation_season,
        "fast_mode": fast,
        "metrics": best_metrics,
    }
    path = save_hyperparams(best_hp, meta=meta)
    return {"path": str(path), "hyperparams": best_hp, **meta}


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibra hiperparâmetros WC no holdout")
    parser.add_argument("--season", type=int, default=settings.wc_validation_season)
    parser.add_argument("--max-candidates", type=int, default=None)
    parser.add_argument("--full-grid", action="store_true", help="Grade completa (~486 combinações)")
    parser.add_argument(
        "--slow",
        action="store_true",
        help="Desativa modo rápido (fase 1+2 em vez de grade monolítica)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/lake/reports/wc_tune_report.json"),
    )
    args = parser.parse_args()

    result = run_tune(
        validation_season=args.season,
        max_candidates=args.max_candidates,
        full_grid=args.full_grid,
        fast=not args.slow,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "path": result["path"],
                "hyperparams": result["hyperparams"].__dict__,
                "metrics": result["metrics"],
                "tuned_at": result["tuned_at"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    m = result["metrics"]
    hp = result["hyperparams"]
    print(f"Salvo: {result['path']}")
    print(f"Relatório: {args.output}")
    print(f"Brier={m['brier']:.4f} acc={m['accuracy']:.3f} n={m['n']}")
    print(f"Distribuição palpites: {m['pred_distribution']}")
    print(f"Pesos ensemble: {m['ensemble_weights']}")
    print(
        f"elo_home_adv={hp.elo_home_adv} home_neutral={hp.home_adv_goals_neutral} "
        f"C={hp.logistic_c} kxl={hp.kxl_blend_weight} draw_floor={hp.draw_prob_floor}"
    )


if __name__ == "__main__":
    main()
