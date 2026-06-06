from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import pandas as pd

from config import settings
from ingest.sofascore.paths import MATCH_STATS_PARQUET
from schemas.national_teams import normalize_national_team

STAT_COLUMNS = (
    "home_xg",
    "away_xg",
    "home_possession_pct",
    "away_possession_pct",
    "home_shots_on_target",
    "away_shots_on_target",
    "home_big_chances",
    "away_big_chances",
    "home_corners",
    "away_corners",
)


def _empty_stats_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "event_id",
            "home_team",
            "away_team",
            "match_date",
            *STAT_COLUMNS,
        ]
    )


def load_raw_match_stats_df(*, stats_dir=None) -> pd.DataFrame:
    from ingest.gcp.lake_store import cloud_lake_enabled, read_layer_snapshot

    if cloud_lake_enabled():
        return read_layer_snapshot("silver_sofascore")

    root = stats_dir or settings.sofascore_stats_dir
    path = root / MATCH_STATS_PARQUET
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_parquet(path).copy()


def normalize_match_stats_snapshot_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    from ingest.gcp.lake_frames import prepare_timestamps_for_bq_parquet

    out = df.copy()
    if "event_id" in out.columns:
        out["event_id"] = pd.to_numeric(out["event_id"], errors="coerce")
    for col in ("home_team", "away_team"):
        if col in out.columns:
            out[col] = out[col].astype("string")
    for col in STAT_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("match_date", "fetched_at"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")
    out = out.drop_duplicates(subset=["event_id"], keep="last")
    return prepare_timestamps_for_bq_parquet(out)


_batch_df: pd.DataFrame | None = None
_batch_depth = 0


def begin_match_stats_batch() -> None:
    global _batch_df, _batch_depth
    if _batch_depth == 0:
        _batch_df = load_raw_match_stats_df()
    _batch_depth += 1


def commit_match_stats_batch() -> None:
    global _batch_df, _batch_depth
    _batch_depth = max(0, _batch_depth - 1)
    if _batch_depth == 0 and _batch_df is not None:
        save_raw_match_stats_df(_batch_df)
        _batch_df = None


@contextmanager
def match_stats_batch_write():
    begin_match_stats_batch()
    try:
        yield
    finally:
        commit_match_stats_batch()


def upsert_match_stats_row(row: dict, *, stats_dir=None) -> None:
    global _batch_df

    new_df = pd.DataFrame([row])
    if _batch_df is not None:
        if _batch_df.empty:
            _batch_df = new_df
        else:
            _batch_df = pd.concat([_batch_df, new_df], ignore_index=True)
            _batch_df = _batch_df.drop_duplicates(subset=["event_id"], keep="last")
        return

    existing = load_raw_match_stats_df(stats_dir=stats_dir)
    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["event_id"], keep="last")
    else:
        combined = new_df
    save_raw_match_stats_df(combined, stats_dir=stats_dir)


def save_raw_match_stats_df(df: pd.DataFrame, *, stats_dir=None) -> None:
    from ingest.gcp.lake_store import cloud_lake_enabled, write_layer_snapshot

    normalized = normalize_match_stats_snapshot_df(df)

    if cloud_lake_enabled():
        write_layer_snapshot("silver_sofascore", normalized)
        return

    root = stats_dir or settings.sofascore_stats_dir
    root.mkdir(parents=True, exist_ok=True)
    path = root / MATCH_STATS_PARQUET
    normalized.to_parquet(path, index=False)


def _prepare_match_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_stats_df()

    out = df.copy()
    required = {"event_id", "home_team", "away_team", *STAT_COLUMNS}
    missing = required - set(out.columns)
    for col in missing:
        out[col] = pd.NA

    out["home_team"] = out["home_team"].map(normalize_national_team)
    out["away_team"] = out["away_team"].map(normalize_national_team)
    for col in STAT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "match_date" in out.columns:
        out["match_date"] = pd.to_datetime(out["match_date"], utc=True, errors="coerce")
    else:
        out["match_date"] = pd.NaT

    return out.dropna(subset=["home_team", "away_team"])


def load_match_stats_history(
    *,
    stats_dir=None,
    before_date: datetime | None = None,
) -> pd.DataFrame:
    df = _prepare_match_stats_df(load_raw_match_stats_df(stats_dir=stats_dir))
    if before_date is not None and not df.empty:
        cutoff = pd.to_datetime(before_date, utc=True)
        dated = df[df["match_date"].notna()]
        if not dated.empty:
            df = dated[dated["match_date"] < cutoff]

    return df.sort_values("match_date").reset_index(drop=True)


def stats_training_summary(df: pd.DataFrame) -> dict:
    teams: set[str] = set()
    if not df.empty:
        teams.update(df["home_team"].tolist())
        teams.update(df["away_team"].tolist())
    dated = df[df["match_date"].notna()] if not df.empty else df
    return {
        "matches": len(df),
        "teams": len(teams),
        "dated_matches": len(dated),
        "date_min": dated["match_date"].min() if not dated.empty else None,
        "date_max": dated["match_date"].max() if not dated.empty else None,
    }
