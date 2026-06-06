from __future__ import annotations

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


def load_match_stats_history(
    *,
    stats_dir=None,
    before_date: datetime | None = None,
) -> pd.DataFrame:
    root = stats_dir or settings.sofascore_stats_dir
    path = root / MATCH_STATS_PARQUET
    if not path.is_file():
        return _empty_stats_df()

    df = pd.read_parquet(path).copy()
    required = {"event_id", "home_team", "away_team", *STAT_COLUMNS}
    missing = required - set(df.columns)
    for col in missing:
        df[col] = pd.NA

    df["home_team"] = df["home_team"].map(normalize_national_team)
    df["away_team"] = df["away_team"].map(normalize_national_team)
    for col in STAT_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
    else:
        df["match_date"] = pd.NaT

    df = df.dropna(subset=["home_team", "away_team"])
    if before_date is not None:
        cutoff = pd.to_datetime(before_date, utc=True)
        dated = df[df["match_date"].notna()]
        if not dated.empty:
            df = dated[dated["match_date"] < cutoff]

    return df.sort_values("match_date").reset_index(drop=True)


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
        "avg_home_xg": round(float(df["home_xg"].mean()), 3) if not df.empty else None,
        "avg_away_xg": round(float(df["away_xg"].mean()), 3) if not df.empty else None,
        "latest_match": dated["match_date"].max().isoformat() if not dated.empty else None,
    }
