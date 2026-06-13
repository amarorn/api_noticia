"""Append de ticks ao vivo Superbet → parquet para histórico e backtest."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

LIVE_TICKS_PARQUET = "live_ticks.parquet"
_WRITE_LOCK = threading.Lock()

_TICK_COLUMNS: dict[str, str] = {
    "event_id": "Int64",
    "home_team": "string",
    "away_team": "string",
    "betradar_id": "string",
    "minute": "Int64",
    "home_score": "Int64",
    "away_score": "Int64",
    "period_label": "string",
    "status": "string",
    "h2h_odd_1": "float64",
    "h2h_odd_x": "float64",
    "h2h_odd_2": "float64",
    "h2h_implied": "string",
    "prob_final_home": "float64",
    "prob_final_draw": "float64",
    "prob_final_away": "float64",
    "over_2_5": "float64",
    "btts_final": "float64",
    "cashout_action": "string",
    "cashout_remaining_ev": "float64",
    "top_aporte_market": "string",
    "top_aporte_outcome": "string",
    "top_aporte_ev": "float64",
    "raw_market_count": "Int64",
    "home_corners": "Int64",
    "away_corners": "Int64",
    "home_red_cards": "Int64",
    "away_red_cards": "Int64",
    "n_sofascore_events": "Int64",
    "home_xg": "float64",
    "away_xg": "float64",
    "home_possession_pct": "float64",
    "away_possession_pct": "float64",
    "ens_prob_final_home": "float64",
    "ens_prob_l1_delta": "float64",
    "captured_at": "datetime64[ns, UTC]",
}


def live_ticks_path() -> Path:
    return settings.bronze_path / "superbet" / LIVE_TICKS_PARQUET


def _normalize_tick_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col, dtype in _TICK_COLUMNS.items():
        if col not in out.columns:
            out[col] = pd.NA
    out = out[list(_TICK_COLUMNS.keys())]
    if "captured_at" in out.columns:
        out["captured_at"] = pd.to_datetime(out["captured_at"], utc=True, errors="coerce")
    for col, dtype in _TICK_COLUMNS.items():
        if col == "captured_at":
            continue
        try:
            out[col] = out[col].astype(dtype)
        except (TypeError, ValueError):
            pass
    return out


def _read_ticks_safe(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return _normalize_tick_df(pd.read_parquet(path))
    except Exception as exc:
        backup = path.with_suffix(f".corrupt.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.parquet")
        try:
            path.rename(backup)
            logger.warning("live_ticks parquet corrompido; backup em %s (%s)", backup, exc)
        except OSError:
            path.unlink(missing_ok=True)
            logger.warning("live_ticks parquet corrompido removido (%s)", exc)
        return None


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    try:
        df.to_parquet(tmp, index=False)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def append_live_tick(
    *,
    event_id: int,
    snapshot: dict[str, Any],
    inplay: dict[str, Any],
    advice: dict[str, Any],
    tick_extra: dict[str, Any] | None = None,
) -> Path | None:
    inplay_stats = snapshot.get("inplay") or {}
    h2h = snapshot.get("h2h_odds") or {}
    cashout = advice.get("cashout") or {}
    aportes = advice.get("aportes") or []
    top_aporte = aportes[0] if aportes else {}
    shadow = inplay.get("ensemble_shadow") or {}

    row = {
        "event_id": event_id,
        "home_team": snapshot.get("home_team"),
        "away_team": snapshot.get("away_team"),
        "betradar_id": snapshot.get("betradar_id"),
        "minute": inplay_stats.get("minute") or inplay.get("minute"),
        "home_score": inplay_stats.get("home_score"),
        "away_score": inplay_stats.get("away_score"),
        "period_label": inplay_stats.get("period_label"),
        "status": inplay_stats.get("status"),
        "h2h_odd_1": h2h.get("1"),
        "h2h_odd_x": h2h.get("X"),
        "h2h_odd_2": h2h.get("2"),
        "h2h_implied": json.dumps(snapshot.get("h2h_implied") or {}, ensure_ascii=False),
        "prob_final_home": inplay.get("prob_final_home"),
        "prob_final_draw": inplay.get("prob_final_draw"),
        "prob_final_away": inplay.get("prob_final_away"),
        "over_2_5": (inplay.get("final_line_probs") or {}).get("over_2_5"),
        "btts_final": inplay.get("btts_final"),
        "cashout_action": cashout.get("action"),
        "cashout_remaining_ev": cashout.get("remaining_ev"),
        "top_aporte_market": top_aporte.get("market"),
        "top_aporte_outcome": top_aporte.get("outcome"),
        "top_aporte_ev": top_aporte.get("expected_value"),
        "raw_market_count": snapshot.get("raw_market_count"),
        "home_corners": inplay_stats.get("home_corners"),
        "away_corners": inplay_stats.get("away_corners"),
        "captured_at": snapshot.get("captured_at")
        or datetime.now(timezone.utc).isoformat(),
    }
    if tick_extra:
        row.update(tick_extra)

    path = live_ticks_path()
    new_df = _normalize_tick_df(pd.DataFrame([row]))

    with _WRITE_LOCK:
        existing = _read_ticks_safe(path)
        combined = pd.concat([existing, new_df], ignore_index=True) if existing is not None else new_df
        _atomic_write_parquet(combined, path)

    return path
