"""Pressão de classificação no grupo (must-win / vaga garantida) a partir de resultados anteriores."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from pipelines.wc_group_standings import build_group_standings
from schemas.national_teams import normalize_national_team

QUALIFY_TOP_N = 2
GROUP_SIZE = 4
GROUP_MATCHDAYS = 3


@dataclass(frozen=True)
class GroupPressure:
    home_must_win: float
    away_must_win: float
    home_secured: float
    away_secured: float
    home_points: float
    away_points: float
    group_matchday: float


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value, utc=True).to_pydatetime()


def _group_col(df: pd.DataFrame) -> str | None:
    if "group_name" in df.columns:
        return "group_name"
    if "group" in df.columns:
        return "group"
    return None


def _result_rows_from_fixtures(
    fixtures_df: pd.DataFrame,
    season: int,
    group_id: str,
    before_date: datetime,
) -> list[dict]:
    gcol = _group_col(fixtures_df)
    if gcol is None:
        return []

    cutoff = _parse_dt(before_date)
    df = fixtures_df.copy()
    df["_dt"] = pd.to_datetime(df["match_date"], utc=True)
    mask = (
        (df["season"] == season)
        & (df[gcol].astype(str).str.upper() == group_id.upper())
        & (df["phase"].fillna("group") == "group")
        & (df["_dt"] < cutoff)
    )
    prior = df.loc[mask].sort_values("_dt")
    rows: list[dict] = []
    for _, row in prior.iterrows():
        hs, aws = int(row["home_score"]), int(row["away_score"])
        if hs > aws:
            label = "1"
        elif hs < aws:
            label = "2"
        else:
            label = "X"
        rows.append(
            {
                "home_team": normalize_national_team(row["home_team"]),
                "away_team": normalize_national_team(row["away_team"]),
                "prediction": label,
                "group": group_id.upper(),
            }
        )
    return rows


def _team_row(standings: list[dict], team: str) -> dict | None:
    target = normalize_national_team(team).casefold()
    for row in standings:
        if normalize_national_team(row["team"]).casefold() == target:
            return row
    return None


def _must_win(points: int, played: int, position: int, leader_pts: int) -> bool:
    remaining = GROUP_MATCHDAYS - played
    if remaining <= 0:
        return False
    max_total = points + remaining * 3
    if position <= QUALIFY_TOP_N and points >= leader_pts:
        return False
    if max_total < leader_pts:
        return True
    if remaining == 1 and position > QUALIFY_TOP_N:
        return True
    if remaining == 1 and points <= 3:
        return True
    return False


def _secured(points: int, played: int, third_pts: int, third_played: int) -> bool:
    if played < 2:
        return False
    third_remaining = GROUP_MATCHDAYS - third_played
    third_max = third_pts + third_remaining * 3
    return points > third_max + 1


def compute_group_pressure(
    fixtures_df: pd.DataFrame,
    *,
    season: int,
    group_name: str,
    home_team: str,
    away_team: str,
    before_date: datetime,
    phase: str = "group",
) -> GroupPressure:
    neutral = GroupPressure(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if phase not in ("group",) or not group_name:
        return neutral

    result_rows = _result_rows_from_fixtures(
        fixtures_df, season, group_name, before_date
    )
    if not result_rows:
        return neutral

    teams: set[str] = set()
    for row in result_rows:
        teams.add(row["home_team"])
        teams.add(row["away_team"])
    teams.add(normalize_national_team(home_team))
    teams.add(normalize_national_team(away_team))

    tables = build_group_standings(
        [{"id": group_name.upper(), "teams": sorted(teams)}],
        result_rows,
    )
    if not tables:
        return neutral

    standings = tables[0]["standings"]
    home_row = _team_row(standings, home_team)
    away_row = _team_row(standings, away_team)
    if not home_row or not away_row:
        return neutral

    leader_pts = standings[0]["points"]
    third = standings[2] if len(standings) > 2 else standings[-1]
    home_must = _must_win(
        home_row["points"],
        home_row["played"],
        home_row["position"],
        leader_pts,
    )
    away_must = _must_win(
        away_row["points"],
        away_row["played"],
        away_row["position"],
        leader_pts,
    )
    home_sec = _secured(
        home_row["points"],
        home_row["played"],
        third["points"],
        third["played"],
    )
    away_sec = _secured(
        away_row["points"],
        away_row["played"],
        third["points"],
        third["played"],
    )
    matchday = float(max(home_row["played"], away_row["played"]))

    return GroupPressure(
        home_must_win=1.0 if home_must else 0.0,
        away_must_win=1.0 if away_must else 0.0,
        home_secured=1.0 if home_sec else 0.0,
        away_secured=1.0 if away_sec else 0.0,
        home_points=float(home_row["points"]),
        away_points=float(away_row["points"]),
        group_matchday=matchday,
    )


def lookup_2026_group(home_team: str, away_team: str) -> str | None:
    from pathlib import Path

    path = Path("data/rounds/wc_2026.json")
    if not path.exists():
        return None
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    home_cf = normalize_national_team(home_team).casefold()
    away_cf = normalize_national_team(away_team).casefold()
    for match in data.get("matches", []):
        g = match.get("group")
        if not g:
            continue
        mh = normalize_national_team(match["home_team"]).casefold()
        ma = normalize_national_team(match["away_team"]).casefold()
        if {mh, ma} == {home_cf, away_cf}:
            return str(g)
    for group in data.get("groups", []):
        teams = {normalize_national_team(t).casefold() for t in group.get("teams", [])}
        if home_cf in teams and away_cf in teams:
            return str(group["id"])
    return None
