import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from pipelines.wc_stats import ELO_INITIAL, WcMatchFeatures, compute_elo_ratings

MAX_GOALS = 6
HOME_ADV_GOALS = 0.15


@dataclass
class PoissonPrediction:
    prob_home: float
    prob_draw: float
    prob_away: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str


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


def predict_poisson(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
) -> PoissonPrediction:
    history = _history_until(fixtures_df, before_date)
    attack, defense, league_avg = _team_attack_defense(history)

    att_h = attack.get(home_team, 1.0)
    att_a = attack.get(away_team, 1.0)
    def_h = defense.get(home_team, 1.0)
    def_a = defense.get(away_team, 1.0)

    lam_home = league_avg * att_h * def_a + HOME_ADV_GOALS
    lam_away = league_avg * att_a * def_h

    if features:
        elo_factor = 1.0 + (features.elo_diff / 2000.0)
        lam_home *= max(0.5, elo_factor)
        lam_away *= max(0.5, 2.0 - elo_factor)

    prob_home = prob_draw = prob_away = 0.0
    best_score = (0, 0)
    best_prob = 0.0

    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = _poisson_prob(i, lam_home) * _poisson_prob(j, lam_away)
            if p > best_prob:
                best_prob = p
                best_score = (i, j)
            if i > j:
                prob_home += p
            elif i == j:
                prob_draw += p
            else:
                prob_away += p

    total = prob_home + prob_draw + prob_away
    if total > 0:
        prob_home /= total
        prob_draw /= total
        prob_away /= total

    return PoissonPrediction(
        prob_home=prob_home,
        prob_draw=prob_draw,
        prob_away=prob_away,
        expected_home_goals=lam_home,
        expected_away_goals=lam_away,
        most_likely_score=f"{best_score[0]}x{best_score[1]}",
    )
