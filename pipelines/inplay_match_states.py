"""Silver: estados in-play por tick (Superbet + label final).

Consolida ``live_ticks.parquet`` com placar final (gold) para retreino
e benchmark segmentado por minuto/placar.

CLI: build-inplay-states [--event-id 12512380]
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from config import settings

MATCH_STATES_PATH = settings.lake_root / "silver" / "inplay" / "match_states.parquet"


def _outcome_label(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "1"
    if home_score < away_score:
        return "2"
    return "X"


def _load_final_labels() -> dict[int, dict[str, int | str]]:
    """Placar final por event_id a partir de gold/superbet/events/*/final.json."""
    labels: dict[int, dict[str, int | str]] = {}
    base = settings.gold_path / "superbet" / "events"
    if not base.exists():
        return labels
    for final_path in base.glob("*/final.json"):
        try:
            data = json.loads(final_path.read_text(encoding="utf-8"))
            eid = int(data["event_id"])
            hs = data.get("home_score")
            aw = data.get("away_score")
            if hs is None or aw is None:
                continue
            hs_i, aw_i = int(hs), int(aw)
            labels[eid] = {
                "home_score_final": hs_i,
                "away_score_final": aw_i,
                "y_final": _outcome_label(hs_i, aw_i),
                "finalized_at": data.get("finalized_at"),
            }
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return labels


def _sofascore_momentum_counts(event_id: int, home: str, away: str) -> dict[str, int]:
    """Conta eventos Sofascore salvos em bronze (se existirem)."""
    from ingest.sofascore.live_momentum import resolve_sofascore_event_id

    ss_id = resolve_sofascore_event_id(home, away)
    if ss_id is None:
        return {"sofascore_event_id": 0, "n_goals_ss": 0, "n_red_cards_ss": 0}

    latest = settings.bronze_path / "sofascore" / "live" / str(ss_id) / "latest.json"
    if not latest.exists():
        return {"sofascore_event_id": ss_id, "n_goals_ss": 0, "n_red_cards_ss": 0}

    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
        events = payload.get("events") or []
    except json.JSONDecodeError:
        return {"sofascore_event_id": ss_id, "n_goals_ss": 0, "n_red_cards_ss": 0}

    n_goals = sum(1 for e in events if e.get("event_type") == "goal")
    n_red = sum(1 for e in events if e.get("event_type") == "red_card")
    return {
        "sofascore_event_id": ss_id,
        "n_goals_ss": n_goals,
        "n_red_cards_ss": n_red,
    }


def build_match_states_from_ticks(
    ticks: pd.DataFrame,
    finals: dict[int, dict[str, int | str]] | None = None,
) -> pd.DataFrame:
    """Enriquece ticks com label final, brier e features derivadas."""
    if ticks.empty:
        return pd.DataFrame()

    finals = finals if finals is not None else _load_final_labels()
    df = ticks.copy()
    df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce").astype("Int64")

    df["home_score_final"] = df["event_id"].map(
        lambda x: finals.get(int(x), {}).get("home_score_final") if pd.notna(x) else None
    )
    df["away_score_final"] = df["event_id"].map(
        lambda x: finals.get(int(x), {}).get("away_score_final") if pd.notna(x) else None
    )
    df["y_final"] = df["event_id"].map(
        lambda x: finals.get(int(x), {}).get("y_final") if pd.notna(x) else None
    )

    def _brier_row(row: pd.Series) -> float | None:
        y = row.get("y_final")
        if y is None or pd.isna(y):
            return None
        p1 = row.get("prob_final_home")
        px = row.get("prob_final_draw")
        p2 = row.get("prob_final_away")
        if any(pd.isna(v) for v in (p1, px, p2)):
            return None
        t1 = 1.0 if y == "1" else 0.0
        tx = 1.0 if y == "X" else 0.0
        t2 = 1.0 if y == "2" else 0.0
        return float(((p1 - t1) ** 2 + (px - tx) ** 2 + (p2 - t2) ** 2) / 3)

    df["brier_model"] = df.apply(_brier_row, axis=1)

    df["minute_bucket"] = pd.cut(
        pd.to_numeric(df["minute"], errors="coerce").fillna(0).astype(int),
        bins=[0, 15, 30, 45, 60, 75, 90, 999],
        labels=["0-15", "15-30", "30-45", "45-60", "60-75", "75-90", "90+"],
        include_lowest=True,
    )

    df["score_state"] = df.apply(
        lambda r: f"{int(r['home_score']) if pd.notna(r.get('home_score')) else 0}-"
        f"{int(r['away_score']) if pd.notna(r.get('away_score')) else 0}",
        axis=1,
    )

    df["built_at"] = datetime.now(UTC)
    return df


def upsert_match_states(*, event_ids: list[int] | None = None) -> Path:
    """Atualiza silver/inplay/match_states.parquet a partir de live_ticks."""
    from ingest.superbet.live_ticks import live_ticks_path

    ticks_path = live_ticks_path()
    if not ticks_path.exists():
        raise FileNotFoundError(f"Sem live ticks: {ticks_path}")

    ticks = pd.read_parquet(ticks_path)
    if event_ids:
        ticks = ticks[ticks["event_id"].isin(event_ids)]

    states = build_match_states_from_ticks(ticks)
    MATCH_STATES_PATH.parent.mkdir(parents=True, exist_ok=True)

    if MATCH_STATES_PATH.exists() and event_ids:
        existing = pd.read_parquet(MATCH_STATES_PATH)
        existing = existing[~existing["event_id"].isin(event_ids)]
        states = pd.concat([existing, states], ignore_index=True)

    states.to_parquet(MATCH_STATES_PATH, index=False)
    return MATCH_STATES_PATH


def summarize_match_states(path: Path | None = None) -> dict:
    """Resumo rápido para benchmark/API."""
    path = path or MATCH_STATES_PATH
    if not path.exists():
        return {"error": "match_states ausente", "path": str(path)}

    df = pd.read_parquet(path)
    labeled = df[df["y_final"].notna()]
    summary: dict = {
        "path": str(path),
        "n_ticks": len(df),
        "n_events": int(df["event_id"].nunique()),
        "n_labeled_ticks": len(labeled),
        "n_labeled_events": int(labeled["event_id"].nunique()) if not labeled.empty else 0,
    }
    if not labeled.empty and labeled["brier_model"].notna().any():
        summary["brier_mean"] = round(float(labeled["brier_model"].mean()), 5)
        by_bucket = (
            labeled.groupby("minute_bucket", observed=True)["brier_model"]
            .mean()
            .round(5)
            .to_dict()
        )
        summary["brier_by_minute_bucket"] = by_bucket
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrói silver in-play match_states")
    parser.add_argument("--event-id", type=int, action="append", dest="event_ids")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    out = upsert_match_states(event_ids=args.event_ids)
    report = summarize_match_states(out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Silver salvo: {out}")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
