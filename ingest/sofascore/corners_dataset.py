from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import settings
from ingest.sofascore.paths import MATCH_STATS_PARQUET
from schemas.national_teams import normalize_national_team


def load_corners_history(
    *,
    stats_dir: Path | None = None,
    before_date: datetime | None = None,
) -> pd.DataFrame:
    """Histórico de escanteios a partir do parquet Sofascore."""
    root = stats_dir or settings.sofascore_stats_dir
    path = root / MATCH_STATS_PARQUET
    if not path.is_file():
        return _empty_corners_df()

    df = pd.read_parquet(path).copy()
    required = {"home_team", "away_team", "home_corners", "away_corners"}
    if not required.issubset(df.columns):
        return _empty_corners_df()

    df["home_team"] = df["home_team"].map(normalize_national_team)
    df["away_team"] = df["away_team"].map(normalize_national_team)
    df["home_corners"] = pd.to_numeric(df["home_corners"], errors="coerce")
    df["away_corners"] = pd.to_numeric(df["away_corners"], errors="coerce")
    df = df.dropna(subset=["home_corners", "away_corners"])
    df["home_corners"] = df["home_corners"].astype(int)
    df["away_corners"] = df["away_corners"].astype(int)

    if "match_date" in df.columns:
        df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
    else:
        df["match_date"] = pd.NaT

    if "season" in df.columns:
        df["season"] = pd.to_numeric(df["season"], errors="coerce")
    else:
        df["season"] = pd.NA
    year_from_date = df["match_date"].dt.year
    missing_season = df["season"].isna()
    df.loc[missing_season, "season"] = year_from_date[missing_season]
    fallback_year = datetime.now(timezone.utc).year
    still_missing = df["season"].isna()
    df.loc[still_missing, "season"] = fallback_year
    df["season"] = df["season"].astype(int)

    if before_date is not None:
        cutoff = pd.to_datetime(before_date, utc=True)
        dated = df[df["match_date"].notna()]
        if not dated.empty:
            df = dated[dated["match_date"] < cutoff]

    return df.reset_index(drop=True)


def corners_training_summary(df: pd.DataFrame) -> dict:
    teams: set[str] = set()
    if not df.empty:
        teams.update(df["home_team"].tolist())
        teams.update(df["away_team"].tolist())
    return {
        "matches": len(df),
        "teams": len(teams),
        "avg_home_corners": round(float(df["home_corners"].mean()), 2) if not df.empty else None,
        "avg_away_corners": round(float(df["away_corners"].mean()), 2) if not df.empty else None,
        "avg_total_corners": round(
            float((df["home_corners"] + df["away_corners"]).mean()), 2
        )
        if not df.empty
        else None,
    }


def _empty_corners_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "event_id",
            "home_team",
            "away_team",
            "match_date",
            "season",
            "home_corners",
            "away_corners",
        ]
    )
