"""Features de notícias RSS para seleções (Sprint 4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from pandas import Timestamp

from pipelines.silver import load_silver
from schemas.national_teams import normalize_national_team

NEWS_FEATURE_NAMES = [
    "wc_news_count_diff",
    "wc_news_sentiment_diff",
    "wc_news_available",
]

DEFAULT_WINDOW_DAYS = 14


def _as_utc(dt: datetime | Timestamp | str | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if isinstance(dt, str):
        parsed = pd.to_datetime(dt, utc=True)
        return parsed.to_pydatetime()
    if isinstance(dt, Timestamp):
        return dt.to_pydatetime()
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    parsed = pd.to_datetime(dt, utc=True)
    return parsed.to_pydatetime()


def _article_teams(row: pd.Series) -> list[str]:
    national = row.get("national_teams_mentioned")
    club = row.get("teams_mentioned")
    teams: list[str] = []
    if isinstance(national, list):
        teams.extend(str(t) for t in national)
    if isinstance(club, list):
        teams.extend(str(t) for t in club)
    return [normalize_national_team(t) for t in teams]


def _mentions_team(teams: list[str], team: str) -> bool:
    target = normalize_national_team(team).casefold()
    return any(normalize_national_team(t).casefold() == target for t in teams)


def _filter_news(
    silver_df: pd.DataFrame,
    before_date: datetime,
    window_days: int,
) -> pd.DataFrame:
    if silver_df.empty:
        return silver_df
    df = silver_df.copy()
    cutoff_end = _as_utc(before_date)
    cutoff_start = cutoff_end - timedelta(days=window_days)
    pub = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    scraped = pd.to_datetime(df["scraped_at"], utc=True, errors="coerce")
    ts = pub.fillna(scraped)
    mask = (ts >= cutoff_start) & (ts < cutoff_end)
    return df.loc[mask.fillna(False)]


def wc_news_feature_vector(
    home_team: str,
    away_team: str,
    before_date: datetime | None = None,
    *,
    silver_df: pd.DataFrame | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> list[float]:
    ref = _as_utc(before_date)
    df = silver_df if silver_df is not None else load_silver()
    windowed = _filter_news(df, ref, window_days)

    if windowed.empty:
        return [0.0, 0.0, 0.0]

    home_count = away_count = 0
    home_sent: list[float] = []
    away_sent: list[float] = []

    for _, row in windowed.iterrows():
        teams = _article_teams(row)
        if not teams:
            continue
        sent = row.get("sentiment_score")
        score = float(sent) if sent is not None and not pd.isna(sent) else 0.0
        if _mentions_team(teams, home_team):
            home_count += 1
            home_sent.append(score)
        if _mentions_team(teams, away_team):
            away_count += 1
            away_sent.append(score)

    if home_count == 0 and away_count == 0:
        return [0.0, 0.0, 0.0]

    home_avg = sum(home_sent) / len(home_sent) if home_sent else 0.0
    away_avg = sum(away_sent) / len(away_sent) if away_sent else 0.0
    return [
        float(home_count - away_count),
        float(home_avg - away_avg),
        1.0,
    ]
