from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.sofascore.paths import MATCH_STATS_PARQUET
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()

JSON_SUFFIX = "_stats.json"


@dataclass(frozen=True)
class CompactStatsReport:
    json_files: int
    rows_written: int
    rows_from_json: int
    rows_from_existing: int
    parquet_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "json_files": self.json_files,
            "rows_written": self.rows_written,
            "rows_from_json": self.rows_from_json,
            "rows_from_existing": self.rows_from_existing,
            "parquet_path": str(self.parquet_path),
        }


def _parse_fetched_at(value: object) -> datetime:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return datetime.min.replace(tzinfo=timezone.utc)
    return parsed.to_pydatetime()


def _load_json_rows(stats_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(stats_dir.glob(f"*{JSON_SUFFIX}")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("sofascore_json_skip", path=str(path), error=str(exc))
            continue
        if not isinstance(payload, dict) or payload.get("event_id") is None:
            logger.warning("sofascore_json_skip", path=str(path), reason="missing_event_id")
            continue
        payload["_source_path"] = str(path)
        payload["_source_mtime"] = path.stat().st_mtime
        rows.append(payload)
    return rows


def _normalize_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    if "event_id" not in out.columns:
        return out

    out["event_id"] = pd.to_numeric(out["event_id"], errors="coerce")
    out = out.dropna(subset=["event_id"])
    out["event_id"] = out["event_id"].astype(int)

    if "home_team" in out.columns:
        out["home_team"] = out["home_team"].map(normalize_national_team)
    if "away_team" in out.columns:
        out["away_team"] = out["away_team"].map(normalize_national_team)

    if "match_date" in out.columns:
        out["match_date"] = pd.to_datetime(out["match_date"], utc=True, errors="coerce")

    if "fetched_at" in out.columns:
        out["_sort_ts"] = out["fetched_at"].map(_parse_fetched_at)
    elif "_source_mtime" in out.columns:
        out["_sort_ts"] = pd.to_datetime(out["_source_mtime"], unit="s", utc=True)
    else:
        out["_sort_ts"] = pd.NaT

    meta_cols = {"_source_path", "_source_mtime", "_sort_ts"}
    out = out.sort_values("_sort_ts", na_position="first")
    out = out.drop_duplicates(subset=["event_id"], keep="last")
    drop_cols = [c for c in meta_cols if c in out.columns]
    return out.drop(columns=drop_cols).reset_index(drop=True)


def compact_match_stats_json(
    *,
    stats_dir: Path | None = None,
    merge_existing: bool = True,
) -> CompactStatsReport:
    """Consolida *_stats.json (e parquet existente) em match_stats.parquet."""
    root = stats_dir or settings.sofascore_stats_dir
    root.mkdir(parents=True, exist_ok=True)
    parquet_path = root / MATCH_STATS_PARQUET

    json_rows = _load_json_rows(root)
    frames: list[pd.DataFrame] = []

    if json_rows:
        frames.append(pd.DataFrame(json_rows))

    existing_rows = 0
    if merge_existing and parquet_path.is_file():
        existing = pd.read_parquet(parquet_path)
        existing_rows = len(existing)
        if not existing.empty:
            frames.append(existing)

    if not frames:
        empty = pd.DataFrame()
        empty.to_parquet(parquet_path, index=False)
        logger.info("sofascore_compact_empty", path=str(parquet_path))
        return CompactStatsReport(
            json_files=len(json_rows),
            rows_written=0,
            rows_from_json=0,
            rows_from_existing=0,
            parquet_path=parquet_path,
        )

    combined = pd.concat(frames, ignore_index=True)
    normalized = _normalize_stats_df(combined)
    normalized.to_parquet(parquet_path, index=False)

    report = CompactStatsReport(
        json_files=len(json_rows),
        rows_written=len(normalized),
        rows_from_json=len(json_rows),
        rows_from_existing=existing_rows,
        parquet_path=parquet_path,
    )
    logger.info("sofascore_compact_done", **report.to_dict())
    return report
