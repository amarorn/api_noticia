"""Benchmark Brier in-play para jogos de clubes (ticks Superbet + fixtures)."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from ingest.superbet.live_ticks import live_ticks_path
from ingest.superbet.team_resolver import classify_live_match
from models.league_dixon_coles import clear_league_model_cache


def _brier_row(row: pd.Series) -> float:
    y = row["y_true"]
    p1, px, p2 = row["prob_final_home"], row["prob_final_draw"], row["prob_final_away"]
    return (
        (p1 - (1.0 if y == "1" else 0.0)) ** 2
        + (px - (1.0 if y == "X" else 0.0)) ** 2
        + (p2 - (1.0 if y == "2" else 0.0)) ** 2
    ) / 3


def _final_score_from_ticks(group: pd.DataFrame) -> tuple[int, int, str] | None:
    g = group.dropna(subset=["home_score", "away_score"]).sort_values("captured_at")
    if g.empty:
        return None
    last = g.iloc[-1]
    try:
        hs, aws = int(last["home_score"]), int(last["away_score"])
    except (TypeError, ValueError):
        return None
    if hs > aws:
        label = "1"
    elif hs < aws:
        label = "2"
    else:
        label = "X"
    return hs, aws, label


def _is_finished_group(group: pd.DataFrame) -> bool:
    statuses = {
        str(s).upper()
        for s in group.get("status", pd.Series(dtype="object")).dropna().tolist()
    }
    if statuses & {"FINISHED", "ENDED", "CLOSED"}:
        return True
    minutes = group["minute"].dropna()
    if minutes.empty:
        return False
    return int(minutes.max()) >= 85


def filter_club_ticks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if "match_kind" in df.columns:
        club_mask = df["match_kind"].fillna("") == "club"
        if club_mask.any():
            return df[club_mask].copy()
    kinds = []
    for _, row in df.iterrows():
        _, _, kind = classify_live_match(str(row.get("home_team", "")), str(row.get("away_team", "")))
        kinds.append(kind)
    out = df.copy()
    out["_match_kind"] = kinds
    return out[out["_match_kind"] == "club"].drop(columns=["_match_kind"])


def compute_league_inplay_brier(*, verbose: bool = False) -> dict[str, Any]:
    path = live_ticks_path()
    if not path.exists():
        return {"error": f"Sem live_ticks: {path}", "n_ticks": 0}

    df = pd.read_parquet(path)
    if df.empty:
        return {"error": "live_ticks vazio", "n_ticks": 0}

    df = filter_club_ticks(df)
    if df.empty:
        return {"error": "Nenhum tick de clube identificado", "n_ticks": 0}

    rows: list[dict[str, Any]] = []
    for eid, group in df.groupby("event_id"):
        if not _is_finished_group(group):
            continue
        final = _final_score_from_ticks(group)
        if final is None:
            continue
        _, _, y_true = final
        valid = group.dropna(subset=["prob_final_home", "prob_final_draw", "prob_final_away"])
        if valid.empty:
            continue
        for _, tick in valid.iterrows():
            rows.append(
                {
                    "event_id": int(eid),
                    "minute": int(tick["minute"]) if pd.notna(tick.get("minute")) else 0,
                    "y_true": y_true,
                    "prob_final_home": float(tick["prob_final_home"]),
                    "prob_final_draw": float(tick["prob_final_draw"]),
                    "prob_final_away": float(tick["prob_final_away"]),
                }
            )

    if not rows:
        return {"error": "Sem ticks resolvidos de clubes", "n_ticks": len(df)}

    eval_df = pd.DataFrame(rows)
    eval_df["brier"] = eval_df.apply(_brier_row, axis=1)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "n_ticks": len(eval_df),
        "n_events": int(eval_df["event_id"].nunique()),
        "brier_mean": round(float(eval_df["brier"].mean()), 5),
        "brier_by_minute_bucket": {},
    }

    eval_df["minute_bucket"] = pd.cut(
        eval_df["minute"].clip(0, 90),
        bins=[0, 15, 30, 45, 60, 75, 90],
        labels=["0-15", "15-30", "30-45", "45-60", "60-75", "75-90"],
    )
    for bucket, grp in eval_df.groupby("minute_bucket", observed=True):
        report["brier_by_minute_bucket"][str(bucket)] = round(float(grp["brier"].mean()), 5)

    if verbose:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def tune_hyperparams_from_report(report: dict[str, Any], output_path: Path) -> dict[str, Any]:
    """Ajuste leve: se Brier > 0.22, aumenta peso de mercado in-play."""
    params_path = Path("data/bolao/league_hyperparams.json")
    current = json.loads(params_path.read_text(encoding="utf-8"))
    brier = report.get("brier_mean")
    if brier is not None and brier > 0.22:
        current["inplay_market_prior_weight"] = min(
            0.65, float(current.get("inplay_market_prior_weight", 0.45)) + 0.05
        )
    current["last_brier"] = brier
    current["updated_at"] = datetime.now(UTC).isoformat()
    current["source"] = "benchmark-league-inplay"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    clear_league_model_cache()
    return current


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Brier in-play — clubes BR")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--tune", action="store_true", help="Atualiza data/bolao/league_hyperparams.json")
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.lake_root / "reports" / "league_inplay_benchmark.json",
    )
    args = parser.parse_args()

    report = compute_league_inplay_brier(verbose=args.verbose)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.tune and "brier_mean" in report:
        tuned = tune_hyperparams_from_report(
            report, Path("data/bolao/league_hyperparams.json")
        )
        report["hyperparams_tuned"] = tuned

    if not args.verbose:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
