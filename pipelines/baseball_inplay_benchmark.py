"""Benchmark Brier do modelo de beisebol in-play a partir de live_ticks + bronze.

Filtra eventos com ``sport_id=20`` nos snapshots bronze e avalia moneyline
(prob_final_home / prob_final_away) contra o placar final observado.

CLI: ``benchmark-baseball-inplay [--verbose]``
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import settings
from ingest.superbet.live_ticks import live_ticks_path


def list_baseball_event_ids(*, sport_id: int | None = None) -> set[int]:
    """IDs com snapshot bronze marcados como beisebol."""
    sid = sport_id if sport_id is not None else settings.baseball_sport_id
    root = settings.bronze_path / "superbet" / "events"
    out: set[int] = set()
    if not root.exists():
        return out
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        latest = folder / "latest.json"
        if not latest.exists():
            continue
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("sport_id") != sid:
            continue
        try:
            out.add(int(folder.name))
        except ValueError:
            continue
    return out


def _final_from_ticks(group: pd.DataFrame) -> tuple[int, int] | None:
    """Último placar conhecido do grupo de ticks (melhor esforço)."""
    g = group.dropna(subset=["home_score", "away_score"]).sort_values("captured_at")
    if g.empty:
        return None
    last = g.iloc[-1]
    try:
        return int(last["home_score"]), int(last["away_score"])
    except (TypeError, ValueError):
        return None


def _is_finished_group(group: pd.DataFrame) -> bool:
    statuses = {
        str(s).upper()
        for s in group.get("status", pd.Series(dtype="object")).dropna().tolist()
    }
    if statuses & {"FINISHED", "ENDED", "CLOSED"}:
        return True
    # Heurística: última entrada ≥ 9 e placar desempate
    minutes = group["minute"].dropna()
    if minutes.empty:
        return False
    last_inning = int(minutes.max())
    final = _final_from_ticks(group)
    if final is None:
        return False
    home, away = final
    return last_inning >= 9 and home != away


def compute_baseball_live_ticks_brier(
    *,
    verbose: bool = False,
    sport_id: int | None = None,
) -> dict[str, Any]:
    """Brier moneyline (2-way) nos ticks de beisebol com resultado resolvido."""
    bb_ids = list_baseball_event_ids(sport_id=sport_id)
    path = live_ticks_path()
    if not path.exists():
        return {"error": f"Sem live_ticks: {path}", "n_events_bronze": len(bb_ids)}
    if not bb_ids:
        return {"error": "Nenhum snapshot bronze de beisebol", "n_events_bronze": 0}

    df = pd.read_parquet(path)
    if df.empty:
        return {"error": "live_ticks vazio", "n_events_bronze": len(bb_ids)}

    # Preferir coluna sport_id quando disponível; fallback aos IDs bronze.
    if "sport_id" in df.columns:
        sid = sport_id if sport_id is not None else settings.baseball_sport_id
        by_col = df["sport_id"].fillna(-1).astype("Int64") == sid
        by_bronze = df["event_id"].isin(bb_ids)
        df = df[by_col | by_bronze].copy()
    else:
        df = df[df["event_id"].isin(bb_ids)].copy()
    if df.empty:
        return {
            "error": "Sem ticks para eventos de beisebol",
            "n_events_bronze": len(bb_ids),
            "n_ticks": 0,
        }

    rows: list[dict[str, Any]] = []
    for eid, group in df.groupby("event_id"):
        if not _is_finished_group(group):
            continue
        final = _final_from_ticks(group)
        if final is None:
            continue
        home_f, away_f = final
        y = 1 if home_f > away_f else 0  # beisebol: sem empate FT (exceto raro)

        g = group.dropna(subset=["prob_final_home", "prob_final_away"]).copy()
        if g.empty:
            continue
        for _, tick in g.iterrows():
            p_home = float(tick["prob_final_home"])
            p_away = float(tick["prob_final_away"])
            s = p_home + p_away
            if s <= 0:
                continue
            p_home /= s
            p_away /= s
            brier = (p_home - y) ** 2 + (p_away - (1 - y)) ** 2
            rows.append(
                {
                    "event_id": int(eid),
                    "minute": int(tick["minute"]) if pd.notna(tick["minute"]) else None,
                    "p_home": p_home,
                    "y_home": y,
                    "brier": brier,
                    "home_score_final": home_f,
                    "away_score_final": away_f,
                }
            )

    if not rows:
        return {
            "error": "Nenhum tick resolvido (jogo finalizado) de beisebol",
            "n_events_bronze": len(bb_ids),
            "n_ticks_baseball": int(len(df)),
            "n_events_with_ticks": int(df["event_id"].nunique()),
        }

    rdf = pd.DataFrame(rows)
    by_inning: dict[str, float] = {}
    for inn, sub in rdf.groupby("minute"):
        if inn is None or (isinstance(inn, float) and np.isnan(inn)):
            continue
        by_inning[str(int(inn))] = round(float(sub["brier"].mean()), 4)

    report: dict[str, Any] = {
        "sport": "baseball",
        "n_events_bronze": len(bb_ids),
        "n_events_resolved": int(rdf["event_id"].nunique()),
        "n_ticks_scored": int(len(rdf)),
        "brier_mean": round(float(rdf["brier"].mean()), 4),
        "brier_by_inning": by_inning,
        "accuracy_mean": round(
            float(((rdf["p_home"] >= 0.5).astype(int) == rdf["y_home"]).mean()),
            4,
        ),
    }
    if verbose:
        report["sample_events"] = (
            rdf.groupby("event_id")
            .agg(
                brier=("brier", "mean"),
                final_home=("home_score_final", "first"),
                final_away=("away_score_final", "first"),
            )
            .reset_index()
            .round(4)
            .to_dict(orient="records")
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Brier beisebol in-play")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--sport-id",
        type=int,
        default=None,
        help="Override BASEBALL_SPORT_ID (padrão config)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Grava relatório JSON neste caminho",
    )
    args = parser.parse_args(argv)
    report = compute_baseball_live_ticks_brier(
        verbose=args.verbose,
        sport_id=args.sport_id,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    return 0 if "error" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
