from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import WcMatchFeatures

MAX_CORNERS_PER_TEAM = 16
DEFAULT_LINES = (7.5, 8.5, 9.5, 10.5, 11.5)


@dataclass
class CornerModelFactors:
    league_avg: float
    home_attack: float
    away_attack: float
    home_defense: float
    away_defense: float
    home_advantage: float
    elo_factor_home: float
    elo_factor_away: float
    lambda_home: float
    lambda_away: float
    training_matches: int
    blend_with_goal_proxy: float

    def as_dict(self) -> dict:
        return {
            "league_avg": round(self.league_avg, 3),
            "home_attack": round(self.home_attack, 3),
            "away_attack": round(self.away_attack, 3),
            "home_defense": round(self.home_defense, 3),
            "away_defense": round(self.away_defense, 3),
            "home_advantage": round(self.home_advantage, 3),
            "elo_factor_home": round(self.elo_factor_home, 3),
            "elo_factor_away": round(self.elo_factor_away, 3),
            "lambda_home": round(self.lambda_home, 3),
            "lambda_away": round(self.lambda_away, 3),
            "training_matches": self.training_matches,
            "blend_with_goal_proxy": round(self.blend_with_goal_proxy, 3),
        }


@dataclass
class CornersPrediction:
    expected_home_corners: float
    expected_away_corners: float
    expected_total_corners: float
    most_likely_score: str
    prob_home_more: float
    prob_draw_corners: float
    prob_away_more: float
    line_probs: dict[str, float]
    total_distribution: dict[int, float]


def _poisson_prob(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _reference_season(df: pd.DataFrame) -> int:
    if df.empty or "season" not in df.columns:
        return datetime.now(timezone.utc).year
    seasons = pd.to_numeric(df["season"], errors="coerce").dropna()
    if seasons.empty:
        return datetime.now(timezone.utc).year
    return int(seasons.max())


def _row_season(row, ref: int) -> int:
    raw = row.get("season") if hasattr(row, "get") else row["season"]
    season = pd.to_numeric(raw, errors="coerce")
    if pd.notna(season):
        return int(season)
    match_date = row.get("match_date") if hasattr(row, "get") else row["match_date"]
    if match_date is not None and not pd.isna(match_date):
        return int(pd.to_datetime(match_date, utc=True).year)
    return ref


def _season_weight(season: int, ref_season: int, half_life: float) -> float:
    if half_life <= 0:
        return 1.0
    years_ago = max(0, ref_season - int(season))
    return 0.5 ** (years_ago / half_life)


def _wmean(pairs: list[tuple[float, float]], default: float = 1.0) -> float:
    if not pairs:
        return default
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return sum(v for v, _ in pairs) / len(pairs)
    return sum(v * w for v, w in pairs) / total_w


def _history_until(corners_df: pd.DataFrame, before_date: datetime | None) -> pd.DataFrame:
    if before_date is None or corners_df.empty:
        return corners_df
    cutoff = pd.to_datetime(before_date, utc=True)
    if "match_date" not in corners_df.columns:
        return corners_df
    dated = corners_df[corners_df["match_date"].notna()].copy()
    if dated.empty:
        return corners_df
    filtered = dated[dated["match_date"] < cutoff]
    return filtered if not filtered.empty else corners_df


def _team_corner_attack_defense(
    corners_df: pd.DataFrame,
    *,
    ref_season: int | None = None,
) -> tuple[dict[str, float], dict[str, float], float]:
    df = corners_df.copy()
    hp = get_wc_hyperparams()
    ref = ref_season if ref_season is not None else _reference_season(df)

    home_corners_w: list[tuple[float, float]] = []
    away_corners_w: list[tuple[float, float]] = []
    teams: set[str] = set()

    for _, row in df.iterrows():
        season = _row_season(row, ref)
        w = _season_weight(season, ref, hp.poisson_season_half_life)
        hc, ac = int(row["home_corners"]), int(row["away_corners"])
        home, away = row["home_team"], row["away_team"]
        teams.add(home)
        teams.add(away)
        home_corners_w.append((hc, w))
        away_corners_w.append((ac, w))

    avg_home = _wmean(home_corners_w, 5.0)
    avg_away = _wmean(away_corners_w, 5.0)
    league_avg = (avg_home + avg_away) / 2.0

    attack: dict[str, float] = {}
    defense: dict[str, float] = {}
    for team in teams:
        att_vals: list[tuple[float, float]] = []
        def_vals: list[tuple[float, float]] = []
        for _, row in df.iterrows():
            season = _row_season(row, ref)
            w = _season_weight(season, ref, hp.poisson_season_half_life)
            if row["home_team"] == team:
                att_vals.append((int(row["home_corners"]) / max(avg_home, 0.5), w))
                def_vals.append((int(row["away_corners"]) / max(avg_away, 0.5), w))
            elif row["away_team"] == team:
                att_vals.append((int(row["away_corners"]) / max(avg_away, 0.5), w))
                def_vals.append((int(row["home_corners"]) / max(avg_home, 0.5), w))
        attack[team] = _wmean(att_vals, 1.0)
        defense[team] = _wmean(def_vals, 1.0)

    return attack, defense, league_avg


def _home_advantage_corners(is_neutral: bool) -> float:
    return get_wc_hyperparams().home_advantage_corners(is_neutral)


def expected_corner_lambdas(
    corners_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    *,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
) -> tuple[float, float, float]:
    """Retorna (lambda_home, lambda_away, league_avg)."""
    history = _history_until(corners_df, before_date)
    if history.empty:
        league_avg = 5.0
        lam_home = league_avg + _home_advantage_corners(
            bool(features.is_neutral) if features else True
        )
        lam_away = league_avg
        return lam_home, lam_away, league_avg

    ref = _reference_season(history)
    attack, defense, league_avg = _team_corner_attack_defense(history, ref_season=ref)

    att_h = attack.get(home_team, 1.0)
    att_a = attack.get(away_team, 1.0)
    def_h = defense.get(home_team, 1.0)
    def_a = defense.get(away_team, 1.0)

    is_neutral = bool(features.is_neutral) if features else True
    home_adv = _home_advantage_corners(is_neutral)
    lam_home = league_avg * att_h * def_a + home_adv
    lam_away = league_avg * att_a * def_h

    if features:
        elo_factor = 1.0 + (features.elo_diff / 2000.0)
        lam_home *= max(0.5, elo_factor)
        lam_away *= max(0.5, 2.0 - elo_factor)

    return lam_home, lam_away, league_avg


def _team_sample_count(
    corners_df: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> int:
    if corners_df.empty:
        return 0
    mask = (corners_df["home_team"] == home_team) | (corners_df["away_team"] == home_team)
    mask |= (corners_df["home_team"] == away_team) | (corners_df["away_team"] == away_team)
    return int(mask.sum())


def blend_with_goal_proxy(
    corner_lam_home: float,
    corner_lam_away: float,
    goal_lam_home: float,
    goal_lam_away: float,
    *,
    league_corner_avg: float,
    league_goal_avg: float,
    sample_matches: int,
    min_samples: int = 8,
) -> tuple[float, float, float]:
    if sample_matches >= min_samples or league_goal_avg <= 0:
        return corner_lam_home, corner_lam_away, 0.0

    scale = league_corner_avg / max(league_goal_avg, 0.5)
    proxy_home = goal_lam_home * scale
    proxy_away = goal_lam_away * scale
    weight = max(0.0, 1.0 - sample_matches / min_samples)
    blended_home = (1.0 - weight) * corner_lam_home + weight * proxy_home
    blended_away = (1.0 - weight) * corner_lam_away + weight * proxy_away
    return blended_home, blended_away, weight


def corner_model_factors(
    corners_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    *,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
    goal_lam_home: float | None = None,
    goal_lam_away: float | None = None,
    league_goal_avg: float | None = None,
) -> CornerModelFactors:
    history = _history_until(corners_df, before_date)
    lam_home, lam_away, league_avg = expected_corner_lambdas(
        corners_df,
        home_team,
        away_team,
        features=features,
        before_date=before_date,
    )

    blend = 0.0
    if goal_lam_home is not None and goal_lam_away is not None and league_goal_avg is not None:
        lam_home, lam_away, blend = blend_with_goal_proxy(
            lam_home,
            lam_away,
            goal_lam_home,
            goal_lam_away,
            league_corner_avg=league_avg,
            league_goal_avg=league_goal_avg,
            sample_matches=_team_sample_count(history, home_team, away_team),
        )

    ref = _reference_season(history) if not history.empty else datetime.now(timezone.utc).year
    attack, defense, _ = _team_corner_attack_defense(history, ref_season=ref) if not history.empty else ({}, {}, league_avg)

    is_neutral = bool(features.is_neutral) if features else True
    home_adv = _home_advantage_corners(is_neutral)
    elo_home = 1.0
    elo_away = 1.0
    if features:
        elo_factor = 1.0 + (features.elo_diff / 2000.0)
        elo_home = max(0.5, elo_factor)
        elo_away = max(0.5, 2.0 - elo_factor)

    return CornerModelFactors(
        league_avg=float(league_avg),
        home_attack=float(attack.get(home_team, 1.0)),
        away_attack=float(attack.get(away_team, 1.0)),
        home_defense=float(defense.get(home_team, 1.0)),
        away_defense=float(defense.get(away_team, 1.0)),
        home_advantage=home_adv,
        elo_factor_home=float(elo_home),
        elo_factor_away=float(elo_away),
        lambda_home=float(lam_home),
        lambda_away=float(lam_away),
        training_matches=len(history),
        blend_with_goal_proxy=float(blend),
    )


def _corner_matrix(lam_home: float, lam_away: float) -> list[tuple[int, int, float]]:
    rows: list[tuple[int, int, float]] = []
    total_mass = 0.0
    for home in range(MAX_CORNERS_PER_TEAM + 1):
        p_home = _poisson_prob(home, lam_home)
        for away in range(MAX_CORNERS_PER_TEAM + 1):
            p = p_home * _poisson_prob(away, lam_away)
            total_mass += p
            rows.append((home, away, p))
    if total_mass <= 0:
        return rows
    return [(h, a, p / total_mass) for h, a, p in rows]


def predict_corners(
    lam_home: float,
    lam_away: float,
    *,
    lines: tuple[float, ...] = DEFAULT_LINES,
) -> CornersPrediction:
    matrix = _corner_matrix(lam_home, lam_away)

    prob_home_more = prob_draw = prob_away_more = 0.0
    best_score = (0, 0)
    best_prob = 0.0
    total_dist: dict[int, float] = {}

    for home, away, prob in matrix:
        total = home + away
        total_dist[total] = total_dist.get(total, 0.0) + prob
        if prob > best_prob:
            best_prob = prob
            best_score = (home, away)
        if home > away:
            prob_home_more += prob
        elif home == away:
            prob_draw += prob
        else:
            prob_away_more += prob

    line_probs: dict[str, float] = {}
    for line in lines:
        threshold = int(line)
        if float(line).is_integer():
            p_over = sum(p for total, p in total_dist.items() if total > threshold)
        else:
            p_over = sum(p for total, p in total_dist.items() if total > threshold)
        line_probs[f"over_{line}"] = p_over
        line_probs[f"under_{line}"] = 1.0 - p_over

    return CornersPrediction(
        expected_home_corners=lam_home,
        expected_away_corners=lam_away,
        expected_total_corners=lam_home + lam_away,
        most_likely_score=f"{best_score[0]}x{best_score[1]}",
        prob_home_more=prob_home_more,
        prob_draw_corners=prob_draw,
        prob_away_more=prob_away_more,
        line_probs=line_probs,
        total_distribution={k: round(v, 6) for k, v in sorted(total_dist.items())},
    )
