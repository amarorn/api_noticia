import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from pipelines.wc_hyperparams import get_wc_hyperparams
from pipelines.wc_stats import WcMatchFeatures

MAX_GOALS = 6


@dataclass
class PoissonPrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str


@dataclass
class GoalModelFactors:
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
    rho: float

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
            "rho": round(self.rho, 4),
        }


def _poisson_prob(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam**k) / math.factorial(k)


def _team_attack_defense(fixtures_df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float], float]:
    df = fixtures_df.copy()
    avg_home = df["home_score"].mean()
    avg_away = df["away_score"].mean()
    league_avg = (avg_home + avg_away) / 2.0

    attacks: dict[str, list[float]] = {}
    defenses: dict[str, list[float]] = {}

    for _, row in df.iterrows():
        hs, aws = int(row["home_score"]), int(row["away_score"])
        home, away = row["home_team"], row["away_team"]
        attacks.setdefault(home, []).append(hs / max(avg_home, 0.5))
        attacks.setdefault(away, []).append(aws / max(avg_away, 0.5))
        defenses.setdefault(home, []).append(aws / max(avg_away, 0.5))
        defenses.setdefault(away, []).append(hs / max(avg_home, 0.5))

    attack = {t: sum(v) / len(v) for t, v in attacks.items()}
    defense = {t: sum(v) / len(v) for t, v in defenses.items()}
    return attack, defense, league_avg


def _history_until(fixtures_df: pd.DataFrame, before_date: datetime | None) -> pd.DataFrame:
    if before_date is None:
        return fixtures_df
    cutoff_dt = pd.to_datetime(before_date, utc=True).to_pydatetime()
    cutoff = cutoff_dt if cutoff_dt.tzinfo else cutoff_dt.replace(tzinfo=timezone.utc)
    history = fixtures_df.copy()
    history["_dt"] = pd.to_datetime(history["match_date"], utc=True)
    filtered = history[history["_dt"] < cutoff].drop(columns=["_dt"])
    return filtered if not filtered.empty else fixtures_df


def expected_lambdas(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
) -> tuple[float, float]:
    history = _history_until(fixtures_df, before_date)
    attack, defense, league_avg = _team_attack_defense(history)

    att_h = attack.get(home_team, 1.0)
    att_a = attack.get(away_team, 1.0)
    def_h = defense.get(home_team, 1.0)
    def_a = defense.get(away_team, 1.0)

    hp = get_wc_hyperparams()
    is_neutral = bool(features.is_neutral) if features else True
    home_adv = hp.home_advantage_goals(is_neutral)
    lam_home = league_avg * att_h * def_a + home_adv
    lam_away = league_avg * att_a * def_h

    if features:
        elo_factor = 1.0 + (features.elo_diff / 2000.0)
        lam_home *= max(0.5, elo_factor)
        lam_away *= max(0.5, 2.0 - elo_factor)

    return lam_home, lam_away


def goal_model_factors(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
    rho: float = 0.0,
) -> GoalModelFactors:
    history = _history_until(fixtures_df, before_date)
    attack, defense, league_avg = _team_attack_defense(history)

    att_h = attack.get(home_team, 1.0)
    att_a = attack.get(away_team, 1.0)
    def_h = defense.get(home_team, 1.0)
    def_a = defense.get(away_team, 1.0)

    hp = get_wc_hyperparams()
    is_neutral = bool(features.is_neutral) if features else True
    home_adv = hp.home_advantage_goals(is_neutral)
    lam_home = league_avg * att_h * def_a + home_adv
    lam_away = league_avg * att_a * def_h
    elo_home = 1.0
    elo_away = 1.0

    if features:
        elo_factor = 1.0 + (features.elo_diff / 2000.0)
        elo_home = max(0.5, elo_factor)
        elo_away = max(0.5, 2.0 - elo_factor)
        lam_home *= elo_home
        lam_away *= elo_away

    return GoalModelFactors(
        league_avg=float(league_avg),
        home_attack=float(att_h),
        away_attack=float(att_a),
        home_defense=float(def_h),
        away_defense=float(def_a),
        home_advantage=home_adv,
        elo_factor_home=float(elo_home),
        elo_factor_away=float(elo_away),
        lambda_home=float(lam_home),
        lambda_away=float(lam_away),
        rho=float(rho),
    )


def dixon_coles_tau(home_goals: int, away_goals: int, lam_home: float, lam_away: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lam_home * lam_away * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lam_home * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + lam_away * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def score_outcome_probs(
    lam_home: float,
    lam_away: float,
    rho: float = 0.0,
) -> PoissonPrediction:
    prob_home = prob_draw = prob_away = 0.0
    best_score = (0, 0)
    best_prob = 0.0
    total_mass = 0.0

    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            base = _poisson_prob(i, lam_home) * _poisson_prob(j, lam_away)
            p = base * dixon_coles_tau(i, j, lam_home, lam_away, rho)
            total_mass += p
            if p > best_prob:
                best_prob = p
                best_score = (i, j)
            if i > j:
                prob_home += p
            elif i == j:
                prob_draw += p
            else:
                prob_away += p

    if total_mass > 0:
        prob_home /= total_mass
        prob_draw /= total_mass
        prob_away /= total_mass

    return PoissonPrediction(
        prob_home=prob_home,
        prob_draw=prob_draw,
        prob_away=prob_away,
        expected_home_goals=lam_home,
        expected_away_goals=lam_away,
        most_likely_score=f"{best_score[0]}x{best_score[1]}",
    )


def score_probability(
    home_goals: int,
    away_goals: int,
    lam_home: float,
    lam_away: float,
    rho: float,
) -> float:
    if home_goals > MAX_GOALS or away_goals > MAX_GOALS:
        return 1e-12
    base = _poisson_prob(home_goals, lam_home) * _poisson_prob(away_goals, lam_away)
    return base * dixon_coles_tau(home_goals, away_goals, lam_home, lam_away, rho)


def predict_poisson(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
) -> PoissonPrediction:
    lam_home, lam_away = expected_lambdas(
        fixtures_df,
        home_team,
        away_team,
        features=features,
        before_date=before_date,
    )
    return score_outcome_probs(lam_home, lam_away, rho=0.0)
