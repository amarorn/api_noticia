"""Congela stats do 1T no intervalo para recalibração do 2T."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from ingest.superbet.live_ticks import live_ticks_path
from ingest.superbet.parser import SuperbetEventSnapshot


@dataclass
class HalftimeFrozenStats:
    event_id: int
    ht_home_score: int
    ht_away_score: int
    home_corners_1h: int
    away_corners_1h: int
    home_yellows_1h: int
    away_yellows_1h: int
    frozen_at: str
    home_team: str = ""
    away_team: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HalftimeFrozenStats:
        return cls(
            event_id=int(data["event_id"]),
            ht_home_score=int(data["ht_home_score"]),
            ht_away_score=int(data["ht_away_score"]),
            home_corners_1h=int(data["home_corners_1h"]),
            away_corners_1h=int(data["away_corners_1h"]),
            home_yellows_1h=int(data["home_yellows_1h"]),
            away_yellows_1h=int(data["away_yellows_1h"]),
            frozen_at=str(data["frozen_at"]),
            home_team=str(data.get("home_team") or ""),
            away_team=str(data.get("away_team") or ""),
        )


def _halftime_dir() -> Path:
    return settings.bronze_path / "superbet" / "halftime"


def _halftime_path(event_id: int) -> Path:
    return _halftime_dir() / f"{event_id}.json"


def _is_halftime_window(minute: int, period_label: str | None) -> bool:
    label = (period_label or "").upper()
    if "HT" in label or "INTERVAL" in label or "HALF" in label:
        return True
    return minute > 45


def _stats_from_snapshot(snapshot: SuperbetEventSnapshot) -> HalftimeFrozenStats | None:
    if not snapshot.inplay:
        return None
    ip = snapshot.inplay
    if not _is_halftime_window(ip.minute, ip.period_label):
        return None
    ht_h = ip.ht_home_score if ip.ht_home_score is not None else ip.home_score
    ht_a = ip.ht_away_score if ip.ht_away_score is not None else ip.away_score
    return HalftimeFrozenStats(
        event_id=snapshot.event_id,
        ht_home_score=int(ht_h),
        ht_away_score=int(ht_a),
        home_corners_1h=int(ip.home_corners),
        away_corners_1h=int(ip.away_corners),
        home_yellows_1h=int(ip.home_yellow_cards),
        away_yellows_1h=int(ip.away_yellow_cards),
        frozen_at=datetime.now(UTC).isoformat(),
        home_team=snapshot.home_team,
        away_team=snapshot.away_team,
    )


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return pd.isna(value)
    except (TypeError, ValueError):
        return False


def _int_scalar(*values: Any, default: int = 0) -> int:
    """Converte escalar (incl. pd.NA) para int sem ambiguidade booleana."""
    for value in values:
        if _is_missing(value):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return default


def _str_scalar(value: Any, default: str = "") -> str:
    if _is_missing(value):
        return default
    return str(value)


def _row_value(row: pd.Series, column: str) -> Any:
    if column not in row.index:
        return None
    return row[column]


def _load_from_ticks(event_id: int) -> HalftimeFrozenStats | None:
    path = live_ticks_path()
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty or "event_id" not in df.columns:
        return None
    df = df[df["event_id"] == event_id]
    if df.empty:
        return None
    if "minute" in df.columns:
        ht_df = df[df["minute"].fillna(0).astype(int) >= 45]
        if not ht_df.empty:
            df = ht_df
    if "captured_at" in df.columns:
        df = df.sort_values("captured_at")
    row = df.iloc[0]
    return HalftimeFrozenStats(
        event_id=int(event_id),
        ht_home_score=_int_scalar(_row_value(row, "home_score")),
        ht_away_score=_int_scalar(_row_value(row, "away_score")),
        home_corners_1h=_int_scalar(_row_value(row, "home_corners")),
        away_corners_1h=_int_scalar(_row_value(row, "away_corners")),
        home_yellows_1h=_int_scalar(
            _row_value(row, "home_yellow_cards"),
            _row_value(row, "home_red_cards"),
        ),
        away_yellows_1h=_int_scalar(
            _row_value(row, "away_yellow_cards"),
            _row_value(row, "away_red_cards"),
        ),
        frozen_at=_str_scalar(_row_value(row, "captured_at"), datetime.now(UTC).isoformat()),
        home_team=_str_scalar(_row_value(row, "home_team")),
        away_team=_str_scalar(_row_value(row, "away_team")),
    )


def load_halftime_stats(event_id: int) -> HalftimeFrozenStats | None:
    path = _halftime_path(event_id)
    if path.exists():
        try:
            return HalftimeFrozenStats.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            pass
    return _load_from_ticks(event_id)


def save_halftime_stats(stats: HalftimeFrozenStats) -> Path:
    out_dir = _halftime_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _halftime_path(stats.event_id)
    path.write_text(json.dumps(stats.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_or_freeze_halftime(
    event_id: int,
    snapshot: SuperbetEventSnapshot,
) -> HalftimeFrozenStats | None:
    """Retorna stats congeladas do 1T; persiste na primeira leitura pós-intervalo."""
    existing = load_halftime_stats(event_id)
    if existing is not None:
        return existing
    fresh = _stats_from_snapshot(snapshot)
    if fresh is None:
        return None
    save_halftime_stats(fresh)
    return fresh
