"""Detecta placar Superbet defasado vs timeline/ticks anteriores."""
from __future__ import annotations

from typing import Any

_GOAL_TYPE = 4


def _timeline_goal_total(timeline: list[dict[str, Any]] | None) -> int:
    return sum(1 for ev in timeline or [] if int(ev.get("type") or 0) == _GOAL_TYPE)


def detect_score_stale(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    scorealarm_timeline: list[dict[str, Any]] | None = None,
    last_tick: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sinaliza quando o snapshot pode estar atrasado em relação a outras fontes."""
    warnings: list[str] = []
    snap_total = int(home_score) + int(away_score)

    sa_goals = _timeline_goal_total(scorealarm_timeline)
    if sa_goals > snap_total:
        warnings.append(
            f"ScoreAlarm registrou {sa_goals} gol(s); Superbet mostra {snap_total}."
        )

    if last_tick:
        lt_h = int(last_tick.get("home_score") or 0)
        lt_a = int(last_tick.get("away_score") or 0)
        lt_min = int(last_tick.get("minute") or 0)
        if lt_h + lt_a > snap_total and lt_min <= minute + 2:
            warnings.append(
                f"Tick anterior {lt_h}×{lt_a} (min {lt_min}); snapshot {home_score}×{away_score}."
            )

    return {
        "score_stale": bool(warnings),
        "warnings": warnings,
        "scorealarm_goals": sa_goals,
        "snapshot_goals": snap_total,
    }


def detect_baseball_score_stale(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    last_tick: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Sinaliza placar de beisebol defasado vs último tick em live_ticks."""
    warnings: list[str] = []
    snap_runs = int(home_score) + int(away_score)
    tick_runs: int | None = None

    if last_tick:
        lt_h = int(last_tick.get("home_score") or 0)
        lt_a = int(last_tick.get("away_score") or 0)
        lt_inning = int(last_tick.get("minute") or 0)
        tick_runs = lt_h + lt_a
        if tick_runs > snap_runs and lt_inning <= inning:
            warnings.append(
                f"Tick anterior {lt_h}×{lt_a} ({lt_inning}I); snapshot {home_score}×{away_score} ({inning}I)."
            )
        if lt_inning > inning:
            warnings.append(
                f"Tick anterior na {lt_inning}I; snapshot ainda na {inning}I."
            )

    return {
        "score_stale": bool(warnings),
        "warnings": warnings,
        "snapshot_runs": snap_runs,
        "tick_runs": tick_runs,
    }


def load_last_live_tick(event_id: int) -> dict[str, Any] | None:
    """Última linha do evento em live_ticks.parquet (best effort)."""
    try:
        import pandas as pd

        from ingest.superbet.live_ticks import live_ticks_path

        path = live_ticks_path()
        if not path.exists():
            return None
        df = pd.read_parquet(path, columns=["event_id", "minute", "home_score", "away_score"])
        sub = df[df["event_id"] == int(event_id)]
        if sub.empty:
            return None
        row = sub.iloc[-1]
        return {
            "minute": int(row["minute"]) if row["minute"] == row["minute"] else 0,
            "home_score": int(row["home_score"]) if row["home_score"] == row["home_score"] else 0,
            "away_score": int(row["away_score"]) if row["away_score"] == row["away_score"] else 0,
        }
    except Exception:
        return None


__all__ = ["detect_baseball_score_stale", "detect_score_stale", "load_last_live_tick"]
