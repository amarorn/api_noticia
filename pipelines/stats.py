from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

FORM_WIN = "V"
FORM_DRAW = "E"
FORM_LOSS = "D"


@dataclass
class TeamSnapshot:
    team: str
    position: int
    points: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_diff: int
    form: str


@dataclass
class MatchStats:
    home: TeamSnapshot
    away: TeamSnapshot
    h2h_home_wins: int
    h2h_draws: int
    h2h_away_wins: int
    h2h_results: list[str]


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value, utc=True).to_pydatetime()


def _result_for_team(row: pd.Series, team: str) -> str:
    home = row["home_team"]
    hs, aws = int(row["home_score"]), int(row["away_score"])
    if team == home:
        if hs > aws:
            return FORM_WIN
        if hs == aws:
            return FORM_DRAW
        return FORM_LOSS
    if hs > aws:
        return FORM_LOSS
    if hs == aws:
        return FORM_DRAW
    return FORM_WIN


def _played_before(fixtures_df: pd.DataFrame, before_date: datetime, season: int | None = None) -> pd.DataFrame:
    df = fixtures_df.copy()
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce", utc=True)
    cutoff = _parse_dt(before_date)
    played = df[df["match_date"] < cutoff]
    if season is not None:
        played = played[played["season"] == season]
    return played


def compute_standings(
    fixtures_df: pd.DataFrame,
    before_date: datetime,
    season: int | None = None,
) -> dict[str, TeamSnapshot]:
    played = _played_before(fixtures_df, before_date, season)
    table: dict[str, dict] = {}

    def _ensure(team: str) -> dict:
        if team not in table:
            table[team] = {
                "points": 0, "played": 0, "wins": 0, "draws": 0, "losses": 0,
                "goals_for": 0, "goals_against": 0, "form": [],
            }
        return table[team]

    for _, row in played.sort_values("match_date").iterrows():
        home, away = row["home_team"], row["away_team"]
        hs, aws = int(row["home_score"]), int(row["away_score"])
        ht, at = _ensure(home), _ensure(away)
        ht["played"] += 1
        at["played"] += 1
        ht["goals_for"] += hs
        ht["goals_against"] += aws
        at["goals_for"] += aws
        at["goals_against"] += hs

        if hs > aws:
            ht["wins"] += 1
            ht["points"] += 3
            ht["form"].append(FORM_WIN)
            at["losses"] += 1
            at["form"].append(FORM_LOSS)
        elif hs < aws:
            at["wins"] += 1
            at["points"] += 3
            at["form"].append(FORM_WIN)
            ht["losses"] += 1
            ht["form"].append(FORM_LOSS)
        else:
            ht["draws"] += 1
            at["draws"] += 1
            ht["points"] += 1
            at["points"] += 1
            ht["form"].append(FORM_DRAW)
            at["form"].append(FORM_DRAW)

    ranked = sorted(
        table.items(),
        key=lambda x: (x[1]["points"], x[1]["goals_for"] - x[1]["goals_against"], x[1]["goals_for"]),
        reverse=True,
    )

    snapshots: dict[str, TeamSnapshot] = {}
    for pos, (team, stats) in enumerate(ranked, start=1):
        form = stats["form"][-5:]
        snapshots[team] = TeamSnapshot(
            team=team,
            position=pos,
            points=stats["points"],
            played=stats["played"],
            wins=stats["wins"],
            draws=stats["draws"],
            losses=stats["losses"],
            goals_for=stats["goals_for"],
            goals_against=stats["goals_against"],
            goal_diff=stats["goals_for"] - stats["goals_against"],
            form="-".join(form) if form else "N/A",
        )
    return snapshots


def compute_h2h(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    before_date: datetime,
    season: int | None = None,
    limit: int = 5,
) -> MatchStats | None:
    played = _played_before(fixtures_df, before_date, season)
    h2h = played[
        ((played["home_team"] == home_team) & (played["away_team"] == away_team))
        | ((played["home_team"] == away_team) & (played["away_team"] == home_team))
    ].sort_values("match_date", ascending=False).head(limit)

    home_wins = draws = away_wins = 0
    results: list[str] = []
    for _, row in h2h.iterrows():
        hs, aws = int(row["home_score"]), int(row["away_score"])
        if hs == aws:
            label = "X"
            draws += 1
        elif (row["home_team"] == home_team and hs > aws) or (row["away_team"] == home_team and aws > hs):
            label = "1"
            home_wins += 1
        else:
            label = "2"
            away_wins += 1
        results.append(label)

    standings = compute_standings(fixtures_df, before_date, season)
    home_snap = standings.get(home_team)
    away_snap = standings.get(away_team)

    if not home_snap or not away_snap:
        return None

    return MatchStats(
        home=home_snap,
        away=away_snap,
        h2h_home_wins=home_wins,
        h2h_draws=draws,
        h2h_away_wins=away_wins,
        h2h_results=results,
    )


def format_stats_context(home: str, away: str, stats: MatchStats | None) -> str:
    if stats is None:
        return ""

    h, a = stats.home, stats.away
    lines = [
        "## Estatísticas pré-jogo",
        "",
        f"### {home} (mandante)",
        f"- Posição: {h.position}º | Pontos: {h.points} | Jogos: {h.played}",
        f"- Vitórias/Empates/Derrotas: {h.wins}/{h.draws}/{h.losses}",
        f"- Gols: {h.goals_for} marcados, {h.goals_against} sofridos (saldo {h.goal_diff:+d})",
        f"- Forma (últimos 5): {h.form}",
        "",
        f"### {away} (visitante)",
        f"- Posição: {a.position}º | Pontos: {a.points} | Jogos: {a.played}",
        f"- Vitórias/Empates/Derrotas: {a.wins}/{a.draws}/{a.losses}",
        f"- Gols: {a.goals_for} marcados, {a.goals_against} sofridos (saldo {a.goal_diff:+d})",
        f"- Forma (últimos 5): {a.form}",
        "",
        "### Confronto direto (últimos jogos)",
        f"- Vitórias {home}: {stats.h2h_home_wins} | Empates: {stats.h2h_draws} | Vitórias {away}: {stats.h2h_away_wins}",
    ]
    if stats.h2h_results:
        lines.append(f"- Sequência recente (do mais recente): {' '.join(stats.h2h_results)}")
    return "\n".join(lines)
