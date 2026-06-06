from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import pandas as pd

from config import settings
from ingest.sofascore.paths import MATCH_ENRICH_PARQUET
from schemas.national_teams import normalize_national_team

ENRICH_COLUMNS = (
    "home_position_competition",
    "away_position_competition",
    "home_points_competition",
    "away_points_competition",
    "home_avgrating_last5",
    "away_avgrating_last5",
    "home_form_points_last5",
    "away_form_points_last5",
    "home_form_win_pct_last5",
    "away_form_win_pct_last5",
    "position_diff",
    "points_diff",
    "avgrating_diff",
    "form_points_diff",
    "home_streak_unbeaten",
    "away_streak_unbeaten",
    "home_streak_wins",
    "away_streak_wins",
    "home_streak_clean_sheets",
    "away_streak_clean_sheets",
    "streak_unbeaten_diff",
    "streak_wins_diff",
    "streak_clean_sheets_diff",
    "h2h_home_wins_all",
    "h2h_away_wins_all",
    "h2h_draws_all",
    "h2h_total_all",
    "h2h_home_win_rate",
    "h2h_away_win_rate",
    "h2h_draw_rate",
    "h2h_home_wins_recent5",
    "h2h_away_wins_recent5",
    "h2h_draws_recent5",
)


def _empty_enrich_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "event_id",
            "home_team",
            "away_team",
            "match_date",
            *ENRICH_COLUMNS,
        ]
    )


def load_raw_enrich_df(*, enrich_dir=None) -> pd.DataFrame:
    from ingest.gcp.lake_store import cloud_lake_enabled, read_layer_snapshot

    if cloud_lake_enabled():
        return read_layer_snapshot("silver_sofascore_enrich")

    root = enrich_dir or settings.sofascore_enrich_dir
    path = root / MATCH_ENRICH_PARQUET
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_parquet(path).copy()


def normalize_enrich_snapshot_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    from ingest.gcp.lake_frames import prepare_timestamps_for_bq_parquet

    out = df.copy()
    if "event_id" in out.columns:
        out["event_id"] = pd.to_numeric(out["event_id"], errors="coerce")
    for col in ("home_team", "away_team"):
        if col in out.columns:
            out[col] = out[col].astype("string")
    for col in ENRICH_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("match_date", "fetched_at"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")
    out = out.drop_duplicates(subset=["event_id"], keep="last")
    return prepare_timestamps_for_bq_parquet(out)


_batch_df: pd.DataFrame | None = None
_batch_depth = 0


def begin_enrich_batch() -> None:
    global _batch_df, _batch_depth
    if _batch_depth == 0:
        _batch_df = load_raw_enrich_df()
    _batch_depth += 1


def commit_enrich_batch() -> None:
    global _batch_df, _batch_depth
    _batch_depth = max(0, _batch_depth - 1)
    if _batch_depth == 0 and _batch_df is not None:
        save_raw_enrich_df(_batch_df)
        _batch_df = None


@contextmanager
def enrich_batch_write():
    begin_enrich_batch()
    try:
        yield
    finally:
        commit_enrich_batch()


def upsert_enrich_row(row: dict, *, enrich_dir=None) -> None:
    global _batch_df

    new_df = pd.DataFrame([row])
    if _batch_df is not None:
        if _batch_df.empty:
            _batch_df = new_df
        else:
            _batch_df = pd.concat([_batch_df, new_df], ignore_index=True)
            _batch_df = _batch_df.drop_duplicates(subset=["event_id"], keep="last")
        return

    existing = load_raw_enrich_df(enrich_dir=enrich_dir)
    if not existing.empty:
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["event_id"], keep="last")
    else:
        combined = new_df
    save_raw_enrich_df(combined, enrich_dir=enrich_dir)


def save_raw_enrich_df(df: pd.DataFrame, *, enrich_dir=None) -> None:
    from ingest.gcp.lake_store import cloud_lake_enabled, write_layer_snapshot

    normalized = normalize_enrich_snapshot_df(df)

    if cloud_lake_enabled():
        write_layer_snapshot("silver_sofascore_enrich", normalized)
        return

    root = enrich_dir or settings.sofascore_enrich_dir
    root.mkdir(parents=True, exist_ok=True)
    path = root / MATCH_ENRICH_PARQUET
    normalized.to_parquet(path, index=False)


def _prepare_enrich_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_enrich_df()

    out = df.copy()
    required = {"event_id", "home_team", "away_team", *ENRICH_COLUMNS}
    missing = required - set(out.columns)
    for col in missing:
        out[col] = pd.NA

    out["home_team"] = out["home_team"].map(normalize_national_team)
    out["away_team"] = out["away_team"].map(normalize_national_team)
    for col in ENRICH_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "match_date" in out.columns:
        out["match_date"] = pd.to_datetime(out["match_date"], utc=True, errors="coerce")
    else:
        out["match_date"] = pd.NaT

    return out.dropna(subset=["home_team", "away_team"])


def load_enrich_history(
    *,
    enrich_dir=None,
    before_date: datetime | None = None,
) -> pd.DataFrame:
    df = _prepare_enrich_df(load_raw_enrich_df(enrich_dir=enrich_dir))
    if before_date is not None and not df.empty:
        cutoff = pd.to_datetime(before_date, utc=True)
        dated = df[df["match_date"].notna()]
        if not dated.empty:
            df = dated[dated["match_date"] < cutoff]

    return df.sort_values("match_date").reset_index(drop=True)


def enrich_training_summary(df: pd.DataFrame) -> dict:
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
