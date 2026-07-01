import bisect
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

import pandas as pd

from models.math_utils import sigmoid
from pipelines.wc_fifa_rankings import fifa_points, load_fifa_rankings
from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_market_features import MARKET_FEATURE_NAMES, market_feature_vector
from pipelines.wc_news_features import NEWS_FEATURE_NAMES, wc_news_feature_vector
from pipelines.wc_group_pressure import (
    GroupPressure,
    compute_group_pressure,
    lookup_2026_group,
)
from pipelines.wc_squad_features import SQUAD_FEATURE_NAMES, squad_feature_vector
from pipelines.wc_sofascore_features import (
    SOFASCORE_FEATURE_NAMES,
    sofascore_feature_vector,
)

EXTRA_FEATURE_NAMES = [
    "fifa_points_diff",
] + MARKET_FEATURE_NAMES


def row_group_name(row: Any) -> str | None:
    """group_name/group de uma linha de fixture, ignorando pd.NA."""
    for key in ("group_name", "group"):
        val = row.get(key) if hasattr(row, "get") else None
        if val is None or pd.isna(val):
            continue
        s = str(val).strip()
        if s:
            return s
    return None

GROUP_PRESSURE_FEATURE_NAMES = [
    "home_must_win",
    "away_must_win",
    "home_secured",
    "away_secured",
    "group_matchday",
]


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
    home_must_win: float = 0.0
    away_must_win: float = 0.0
    home_secured: float = 0.0
    away_secured: float = 0.0
    group_matchday: float = 0.0
    # Features enriquecidas (disponíveis apenas para jogos atuais/simulações)
    form_points_diff: float = 0.0
    streak_unbeaten_diff: float = 0.0
    streak_wins_diff: float = 0.0
    h2h_home_win_rate_all: float = 0.0
    h2h_home_wins_recent5: int = 0
    avgrating_diff: float = 0.0
    position_diff: float = 0.0
    points_diff: float = 0.0
    fifa_points_diff: float = 0.0


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


def _update_elo(rating: float, expected: float, actual: float, k: float = 32.0) -> float:
    return rating + k * (actual - expected)


@dataclass
class EloTimeline:
    """Timeline de ratings Elo pré-computada para lookup rápido."""

    team_dates: dict[str, list[datetime]]
    team_ratings: dict[str, list[float]]


def precompute_elo_timeline(fixtures_df: pd.DataFrame) -> EloTimeline:
    """Pré-computa ratings Elo de forma incremental para consulta rápida.

    Itera uma única vez sobre o dataframe ordenado por data, atualizando
    ratings após cada jogo. O resultado permite consultar o rating de
    qualquer time em qualquer data com busca binária O(log n).
    """
    df = fixtures_df.sort_values("match_date")
    hp = get_wc_hyperparams()
    ratings: dict[str, float] = {}

    team_dates: dict[str, list[datetime]] = {}
    team_ratings: dict[str, list[float]] = {}

    def _record(team: str, date: datetime, rating: float) -> None:
        team_dates.setdefault(team, []).append(date)
        team_ratings.setdefault(team, []).append(rating)

    def _get(team: str) -> float:
        return ratings.setdefault(team, hp.elo_initial)

    cols = {c: i for i, c in enumerate(df.columns)}
    ht_idx = cols.get("home_team")
    at_idx = cols.get("away_team")
    hs_idx = cols.get("home_score")
    aws_idx = cols.get("away_score")
    neutral_idx = cols.get("is_neutral")
    date_idx = cols.get("match_date")

    for tup in df.itertuples(index=False):
        home = tup[ht_idx] if ht_idx is not None else tup.home_team
        away = tup[at_idx] if at_idx is not None else tup.away_team
        rh = _get(home)
        ra = _get(away)

        is_neutral = bool(tup[neutral_idx]) if neutral_idx is not None else True
        if is_neutral:
            home_adv = hp.elo_home_adv * 0.35
        else:
            home_adv = hp.elo_home_adv
        rh_adj = rh + home_adv
        exp_home = _expected_score(rh_adj, ra)
        exp_away = 1.0 - exp_home

        hs = int(tup[hs_idx]) if hs_idx is not None else int(tup.home_score)
        aws = int(tup[aws_idx]) if aws_idx is not None else int(tup.away_score)
        if hs > aws:
            act_home, act_away = 1.0, 0.0
        elif hs < aws:
            act_home, act_away = 0.0, 1.0
        else:
            act_home, act_away = 0.5, 0.5

        new_rh = _update_elo(rh, exp_home, act_home, k=hp.elo_k)
        new_ra = _update_elo(ra, exp_away, act_away, k=hp.elo_k)

        ratings[home] = new_rh
        ratings[away] = new_ra

        match_date = _parse_dt(tup[date_idx]) if date_idx is not None else _parse_dt(tup.match_date)
        _record(home, match_date, new_rh)
        _record(away, match_date, new_ra)

    return EloTimeline(team_dates=team_dates, team_ratings=team_ratings)


def get_elo_at_date(timeline: EloTimeline, team: str, before_date: datetime) -> float:
    """Retorna o rating Elo de um time imediatamente antes de uma data.

    Usa busca binária sobre a timeline pré-computada. Se o time nunca
    jogou, retorna o rating inicial (1500 por padrão).
    """
    dates = timeline.team_dates.get(team)
    if not dates:
        return get_wc_hyperparams().elo_initial

    cutoff = _parse_dt(before_date)
    # Encontra o índice mais à direita onde date < cutoff
    idx = bisect.bisect_left(dates, cutoff) - 1
    if idx < 0:
        return get_wc_hyperparams().elo_initial

    return timeline.team_ratings[team][idx]


def compute_elo_ratings(
    fixtures_df: pd.DataFrame,
    before_date: datetime | None = None,
) -> dict[str, float]:
    df = fixtures_df.copy()
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    if before_date:
        df = _played_before(df, before_date)
    df = df.sort_values("match_date")

    hp = get_wc_hyperparams()
    ratings: dict[str, float] = {}

    def _get(team: str) -> float:
        return ratings.setdefault(team, hp.elo_initial)

    # Usa itertuples (mais rápido que iterrows) com nomes normalizados
    cols = {c: i for i, c in enumerate(df.columns)}
    ht_idx = cols.get("home_team")
    at_idx = cols.get("away_team")
    hs_idx = cols.get("home_score")
    aws_idx = cols.get("away_score")
    neutral_idx = cols.get("is_neutral")

    for tup in df.itertuples(index=False):
        home = tup[ht_idx] if ht_idx is not None else tup.home_team
        away = tup[at_idx] if at_idx is not None else tup.away_team
        rh = _get(home)
        ra = _get(away)

        is_neutral = bool(tup[neutral_idx]) if neutral_idx is not None else True
        if is_neutral:
            home_adv = hp.elo_home_adv * 0.35
        else:
            home_adv = hp.elo_home_adv
        rh_adj = rh + home_adv
        exp_home = _expected_score(rh_adj, ra)
        exp_away = 1.0 - exp_home

        hs = int(tup[hs_idx]) if hs_idx is not None else int(tup.home_score)
        aws = int(tup[aws_idx]) if aws_idx is not None else int(tup.away_score)
        if hs > aws:
            act_home, act_away = 1.0, 0.0
        elif hs < aws:
            act_home, act_away = 0.0, 1.0
        else:
            act_home, act_away = 0.5, 0.5

        ratings[home] = _update_elo(rh, exp_home, act_home, k=hp.elo_k)
        ratings[away] = _update_elo(ra, exp_away, act_away, k=hp.elo_k)

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


def _resolve_group_name(
    home_team: str,
    away_team: str,
    season: int | None,
    group_name: str | None,
) -> str | None:
    if group_name:
        return str(group_name)
    if season == 2026:
        return lookup_2026_group(home_team, away_team)
    return None

def build_match_features(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    before_date: datetime | None = None,
    phase: str = "group",
    is_neutral: bool = True,
    season: int | None = None,
    group_name: str | None = None,
    enrich_data: dict[str, Any] | None = None,
    elo_timeline: EloTimeline | None = None,
) -> WcMatchFeatures:
    ref_date = before_date or datetime.now(timezone.utc)
    played = _played_before(fixtures_df, ref_date)
    # Normalizar match_date para evitar TypeError com tipos mistos (str vs Timestamp)
    if not played.empty and "match_date" in played.columns:
        played = played.copy()
        played["match_date"] = pd.to_datetime(played["match_date"], errors="coerce")

    hp = get_wc_hyperparams()
    if elo_timeline is not None:
        rh = get_elo_at_date(elo_timeline, home_team, ref_date)
        ra = get_elo_at_date(elo_timeline, away_team, ref_date)
    else:
        elo = compute_elo_ratings(played)
        rh = elo.get(home_team, hp.elo_initial)
        ra = elo.get(away_team, hp.elo_initial)

    h2h = compute_wc_h2h(played, home_team, away_team)
    gf_h, ga_h, form_h = _team_rates(played, home_team)
    gf_a, ga_a, form_a = _team_rates(played, away_team)

    eff_season = season
    if eff_season is None and not played.empty and "season" in played.columns:
        eff_season = int(played["season"].max())
    if eff_season is None:
        eff_season = ref_date.year

    gid = _resolve_group_name(home_team, away_team, eff_season, group_name)
    pressure = GroupPressure(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if gid and phase == "group":
        pressure = compute_group_pressure(
            fixtures_df,
            season=eff_season,
            group_name=gid,
            home_team=home_team,
            away_team=away_team,
            before_date=ref_date,
            phase=phase,
        )

    # Busca pontos FIFA ao vivo se disponível
    fifa_points_diff = 0.0
    try:
        from ingest.fifa.rankings_live import get_team_points_live
        hp_live = get_team_points_live(home_team)
        ap_live = get_team_points_live(away_team)
        if hp_live is not None and ap_live is not None:
            fifa_points_diff = round(hp_live - ap_live, 2)
    except Exception:
        pass

    # Preenche dados enriquecidos se fornecidos
    enrich = enrich_data or {}

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
        home_must_win=pressure.home_must_win,
        away_must_win=pressure.away_must_win,
        home_secured=pressure.home_secured,
        away_secured=pressure.away_secured,
        group_matchday=pressure.group_matchday,
        form_points_diff=enrich.get("form_points_diff", 0.0),
        streak_unbeaten_diff=enrich.get("streak_unbeaten_diff", 0.0),
        streak_wins_diff=enrich.get("streak_wins_diff", 0.0),
        h2h_home_win_rate_all=enrich.get("h2h_home_win_rate", 0.0),
        h2h_home_wins_recent5=enrich.get("h2h_home_wins_recent5", 0),
        avgrating_diff=enrich.get("avgrating_diff", 0.0),
        position_diff=enrich.get("position_diff", 0.0),
        points_diff=enrich.get("points_diff", 0.0),
        fifa_points_diff=fifa_points_diff,
    )


def group_pressure_from_features(f: WcMatchFeatures) -> GroupPressure:
    return GroupPressure(
        home_must_win=f.home_must_win,
        away_must_win=f.away_must_win,
        home_secured=f.home_secured,
        away_secured=f.away_secured,
        home_points=0.0,
        away_points=0.0,
        group_matchday=f.group_matchday,
    )


ENRICH_FEATURE_NAMES = [
    "form_points_diff",
    "streak_unbeaten_diff",
    "streak_wins_diff",
    "h2h_home_win_rate_all",
    "h2h_home_wins_recent5",
    "avgrating_diff",
    "position_diff",
    "points_diff",
    "fifa_points_diff_live",
]


def features_to_vector(
    f: WcMatchFeatures,
    before_date: datetime | None = None,
) -> list[float]:
    base = [
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
        f.home_must_win,
        f.away_must_win,
        f.home_secured,
        f.away_secured,
        f.group_matchday,
    ]
    rankings = load_fifa_rankings()
    fifa_diff = fifa_points(f.home_team, rankings) - fifa_points(f.away_team, rankings)
    # Usa fifa_points_diff_live se disponível, senão usa o estático
    effective_fifa_diff = f.fifa_points_diff if f.fifa_points_diff != 0.0 else fifa_diff
    return (
        base
        + [effective_fifa_diff]
        + market_feature_vector(f.home_team, f.away_team)
        + squad_feature_vector(f.home_team, f.away_team)
        + wc_news_feature_vector(f.home_team, f.away_team, before_date=before_date)
        + sofascore_feature_vector(f.home_team, f.away_team, before_date=before_date)
        + [
            f.form_points_diff,
            f.streak_unbeaten_diff,
            f.streak_wins_diff,
            f.h2h_home_win_rate_all,
            f.h2h_home_wins_recent5,
            f.avgrating_diff,
            f.position_diff,
            f.points_diff,
            effective_fifa_diff,
        ]
    )


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
] + GROUP_PRESSURE_FEATURE_NAMES + EXTRA_FEATURE_NAMES + SQUAD_FEATURE_NAMES + NEWS_FEATURE_NAMES + SOFASCORE_FEATURE_NAMES + ENRICH_FEATURE_NAMES


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
    if f.group_matchday > 0 or f.home_must_win or f.away_must_win:
        lines.extend(
            [
                "",
                "### Contexto do grupo",
                f"- Rodada simulada no grupo: {int(f.group_matchday)}",
                f"- {f.home_team} precisa vencer: {'sim' if f.home_must_win else 'não'}",
                f"- {f.away_team} precisa vencer: {'sim' if f.away_must_win else 'não'}",
            ]
        )
    return "\n".join(lines)
