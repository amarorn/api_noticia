from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from ingest.sofascore.stats_dataset import STAT_COLUMNS, load_match_stats_history

SOFASCORE_FEATURE_NAMES = [
    "sofa_xg_for_diff_last5",
    "sofa_xg_against_diff_last5",
    "sofa_possession_diff_last5",
    "sofa_shots_on_target_diff_last5",
    "sofa_big_chances_diff_last5",
    "sofa_stats_available",
]

ROLLING_WINDOW = 5
MIN_TEAM_MATCHES = 2


@dataclass(frozen=True)
class TeamRollingStats:
    xg_for: float
    xg_against: float
    possession: float
    shots_on_target: float
    big_chances: float
    samples: int


def _team_perspective_rows(df: pd.DataFrame, team: str) -> pd.DataFrame:
    if df.empty:
        return df

    home = df[df["home_team"] == team].copy()
    away = df[df["away_team"] == team].copy()

    home["xg_for"] = home["home_xg"]
    home["xg_against"] = home["away_xg"]
    home["possession"] = home["home_possession_pct"]
    home["shots_on_target"] = home["home_shots_on_target"]
    home["big_chances"] = home["home_big_chances"]

    away["xg_for"] = away["away_xg"]
    away["xg_against"] = away["home_xg"]
    away["possession"] = away["away_possession_pct"]
    away["shots_on_target"] = away["away_shots_on_target"]
    away["big_chances"] = away["away_big_chances"]

    cols = ["match_date", "xg_for", "xg_against", "possession", "shots_on_target", "big_chances"]
    combined = pd.concat([home[cols], away[cols]], ignore_index=True)
    return combined.sort_values("match_date")


def team_rolling_stats(
    df: pd.DataFrame,
    team: str,
    *,
    window: int = ROLLING_WINDOW,
) -> TeamRollingStats | None:
    rows = _team_perspective_rows(df, team)
    if rows.empty:
        return None

    usable = rows.dropna(subset=["xg_for", "xg_against"])
    if len(usable) < MIN_TEAM_MATCHES:
        return None

    tail = usable.tail(window)

    def _mean(col: str) -> float:
        series = pd.to_numeric(tail[col], errors="coerce").dropna()
        return float(series.mean()) if not series.empty else 0.0

    return TeamRollingStats(
        xg_for=_mean("xg_for"),
        xg_against=_mean("xg_against"),
        possession=_mean("possession"),
        shots_on_target=_mean("shots_on_target"),
        big_chances=_mean("big_chances"),
        samples=len(tail),
    )


def sofascore_feature_vector(
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    stats_df: pd.DataFrame | None = None,
) -> list[float]:
    df = stats_df if stats_df is not None else load_match_stats_history(before_date=before_date)
    home = team_rolling_stats(df, home_team)
    away = team_rolling_stats(df, away_team)

    if home is None or away is None:
        return [0.0] * (len(SOFASCORE_FEATURE_NAMES) - 1) + [0.0]

    return [
        home.xg_for - away.xg_for,
        home.xg_against - away.xg_against,
        home.possession - away.possession,
        home.shots_on_target - away.shots_on_target,
        home.big_chances - away.big_chances,
        1.0,
    ]
