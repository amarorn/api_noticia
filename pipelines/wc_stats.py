from dataclasses import dataclass
from datetime import datetime, timezone
import math

import pandas as pd

from models.math_utils import sigmoid

ELO_INITIAL = 1500.0
ELO_K = 32.0
ELO_HOME_ADV = 65.0


@dataclass
class EloRating:
    team: str
    rating: float


@dataclass
class WcH2H:
    home_wins: int
    draws: int
    away_wins: int
    total: int
    avg_home_goals: float
    avg_away_goals: float
    last_results: list[str]


@dataclass
class WcMatchFeatures:
    home_team: str
    away_team: str
    elo_home: float
    elo_away: float
    elo_diff: float
    h2h_home_wins: int
    h2h_draws: int
    h2h_away_wins: int
    h2h_total: int
    home_goals_rate: float
    away_goals_rate: float
    home_conceded_rate: float
    away_conceded_rate: float
    home_form: str
    away_form: str
    phase_knockout: int
    is_neutral: int


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return pd.to_datetime(value, utc=True).to_pydatetime()


def _played_before(df: pd.DataFrame, before_date: datetime) -> pd.DataFrame:
    cutoff = _parse_dt(before_date)
    played = df.copy()
    played["_date"] = pd.to_datetime(played["match_date"], utc=True)
    return played[played["_date"] < cutoff].drop(columns=["_date"])


def _expected_score(rating_a: float, rating_b: float) -> float:
    return sigmoid((rating_a - rating_b) / 400.0 * math.log(10))


def _update_elo(rating: float, expected: float, actual: float) -> float:
    return rating + ELO_K * (actual - expected)


def compute_elo_ratings(
    fixtures_df: pd.DataFrame,
    before_date: datetime | None = None,
) -> dict[str, float]:
    df = fixtures_df.copy()
    if before_date:
        df = _played_before(df, before_date)
    df = df.sort_values("match_date")

    ratings: dict[str, float] = {}

    def _get(team: str) -> float:
        return ratings.setdefault(team, ELO_INITIAL)

    for _, row in df.iterrows():
        home = row["home_team"]
        away = row["away_team"]
        rh = _get(home)
        ra = _get(away)

        rh_adj = rh + ELO_HOME_ADV
        exp_home = _expected_score(rh_adj, ra)
        exp_away = 1.0 - exp_home

        hs, aws = int(row["home_score"]), int(row["away_score"])
        if hs > aws:
            act_home, act_away = 1.0, 0.0
        elif hs < aws:
            act_home, act_away = 0.0, 1.0
        else:
            act_home, act_away = 0.5, 0.5

        ratings[home] = _update_elo(rh, exp_home, act_home)
        ratings[away] = _update_elo(ra, exp_away, act_away)

    return ratings


def compute_wc_h2h(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    before_date: datetime | None = None,
) -> WcH2H:
    df = fixtures_df.copy()
    if before_date:
        df = _played_before(df, before_date)

    h2h = df[
        ((df["home_team"] == home_team) & (df["away_team"] == away_team))
        | ((df["home_team"] == away_team) & (df["away_team"] == home_team))
    ].sort_values("match_date")

    home_wins = draws = away_wins = 0
    home_goals: list[float] = []
    away_goals: list[float] = []
    results: list[str] = []

    for _, row in h2h.iterrows():
        hs, aws = int(row["home_score"]), int(row["away_score"])
        if row["home_team"] == home_team:
            home_goals.append(hs)
            away_goals.append(aws)
            if hs > aws:
                home_wins += 1
                results.append("1")
            elif hs == aws:
                draws += 1
                results.append("X")
            else:
                away_wins += 1
                results.append("2")
        else:
            home_goals.append(aws)
            away_goals.append(hs)
            if aws > hs:
                home_wins += 1
                results.append("1")
            elif aws == hs:
                draws += 1
                results.append("X")
            else:
                away_wins += 1
                results.append("2")

    total = len(h2h)
    return WcH2H(
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
        total=total,
        avg_home_goals=sum(home_goals) / total if total else 0.0,
        avg_away_goals=sum(away_goals) / total if total else 0.0,
        last_results=results[-5:],
    )


def _team_rates(df: pd.DataFrame, team: str) -> tuple[float, float, str]:
    team_games = df[(df["home_team"] == team) | (df["away_team"] == team)].sort_values("match_date")
    if team_games.empty:
        return 1.0, 1.0, "N/A"

    scored, conceded, form = 0, 0, []
    for _, row in team_games.tail(10).iterrows():
        hs, aws = int(row["home_score"]), int(row["away_score"])
        if row["home_team"] == team:
            scored += hs
            conceded += aws
            form.append("V" if hs > aws else ("E" if hs == aws else "D"))
        else:
            scored += aws
            conceded += hs
            form.append("V" if aws > hs else ("E" if aws == hs else "D"))

    n = len(team_games.tail(10))
    return scored / n, conceded / n, "-".join(form[-5:])


def build_match_features(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    before_date: datetime | None = None,
    phase: str = "group",
    is_neutral: bool = True,
) -> WcMatchFeatures:
    ref_date = before_date or datetime.now(timezone.utc)
    played = _played_before(fixtures_df, ref_date)
    elo = compute_elo_ratings(played)
    h2h = compute_wc_h2h(played, home_team, away_team)

    rh = elo.get(home_team, ELO_INITIAL)
    ra = elo.get(away_team, ELO_INITIAL)
    gf_h, ga_h, form_h = _team_rates(played, home_team)
    gf_a, ga_a, form_a = _team_rates(played, away_team)

    return WcMatchFeatures(
        home_team=home_team,
        away_team=away_team,
        elo_home=rh,
        elo_away=ra,
        elo_diff=rh - ra,
        h2h_home_wins=h2h.home_wins,
        h2h_draws=h2h.draws,
        h2h_away_wins=h2h.away_wins,
        h2h_total=h2h.total,
        home_goals_rate=gf_h,
        away_goals_rate=gf_a,
        home_conceded_rate=ga_h,
        away_conceded_rate=ga_a,
        home_form=form_h,
        away_form=form_a,
        phase_knockout=1 if phase not in ("group",) else 0,
        is_neutral=1 if is_neutral else 0,
    )


def features_to_vector(f: WcMatchFeatures) -> list[float]:
    return [
        f.elo_diff,
        f.h2h_home_wins,
        f.h2h_draws,
        f.h2h_away_wins,
        f.h2h_total,
        f.home_goals_rate,
        f.away_goals_rate,
        f.home_conceded_rate,
        f.away_conceded_rate,
        f.home_form.count("V") - f.away_form.count("V"),
        f.phase_knockout,
        f.is_neutral,
    ]


FEATURE_NAMES = [
    "elo_diff",
    "h2h_home_wins",
    "h2h_draws",
    "h2h_away_wins",
    "h2h_total",
    "home_goals_rate",
    "away_goals_rate",
    "home_conceded_rate",
    "away_conceded_rate",
    "form_wins_diff",
    "phase_knockout",
    "is_neutral",
]


def format_wc_context(f: WcMatchFeatures, h2h: WcH2H | None = None) -> str:
    lines = [
        "## Estatísticas pré-jogo (Copa do Mundo)",
        "",
        f"### {f.home_team}",
        f"- Elo: {f.elo_home:.0f} | Gols/jogo: {f.home_goals_rate:.2f} | Sofridos/jogo: {f.home_conceded_rate:.2f}",
        f"- Forma recente: {f.home_form}",
        "",
        f"### {f.away_team}",
        f"- Elo: {f.elo_away:.0f} | Gols/jogo: {f.away_goals_rate:.2f} | Sofridos/jogo: {f.away_conceded_rate:.2f}",
        f"- Forma recente: {f.away_form}",
        "",
        f"### Confronto direto em Copas ({f.h2h_total} jogos)",
        f"- Vitórias {f.home_team}: {f.h2h_home_wins} | Empates: {f.h2h_draws} | Vitórias {f.away_team}: {f.h2h_away_wins}",
    ]
    if h2h and h2h.last_results:
        lines.append(f"- Sequência: {' '.join(h2h.last_results)}")
    return "\n".join(lines)
