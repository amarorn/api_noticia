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


def _reference_season(df: pd.DataFrame) -> int:
    if df.empty or "season" not in df.columns:
        return datetime.now(timezone.utc).year
    return int(df["season"].max())


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


def _team_attack_defense(
    fixtures_df: pd.DataFrame,
    *,
    ref_season: int | None = None,
) -> tuple[dict[str, float], dict[str, float], float]:
    df = fixtures_df.copy()
    hp = get_wc_hyperparams()
    ref = ref_season if ref_season is not None else _reference_season(df)

    # Guarda de sanidade: remover linhas com scores impossíveis para futebol.
    # Dados de cricket/outros esportes às vezes se infiltram no dataset.
    _MAX_FOOTBALL_SCORE = 15
    pre_len = len(df)
    df = df[(df["home_score"] <= _MAX_FOOTBALL_SCORE) & (df["away_score"] <= _MAX_FOOTBALL_SCORE)]
    if len(df) < pre_len:
        import structlog
        structlog.get_logger().warning(
            "poisson_outliers_removidos",
            removidos=pre_len - len(df),
            max_score_permitido=_MAX_FOOTBALL_SCORE,
        )

    df["_w"] = df["season"].fillna(ref).astype(int).apply(
        lambda s: _season_weight(s, ref, hp.poisson_season_half_life)
    )

    avg_home = float((df["home_score"] * df["_w"]).sum() / max(df["_w"].sum(), 1e-12))
    avg_away = float((df["away_score"] * df["_w"]).sum() / max(df["_w"].sum(), 1e-12))
    league_avg = (avg_home + avg_away) / 2.0

    # Attack e defesa como mandante
    home_att = df.groupby("home_team").apply(
        lambda g: float((g["home_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12)) / max(avg_home, 0.5),
        include_groups=False,
    )
    home_def = df.groupby("home_team").apply(
        lambda g: float((g["away_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12)) / max(avg_away, 0.5),
        include_groups=False,
    )

    # Attack e defesa como visitante
    away_att = df.groupby("away_team").apply(
        lambda g: float((g["away_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12)) / max(avg_away, 0.5),
        include_groups=False,
    )
    away_def = df.groupby("away_team").apply(
        lambda g: float((g["home_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12)) / max(avg_home, 0.5),
        include_groups=False,
    )

    teams: set[str] = set(df["home_team"]).union(set(df["away_team"]))
    attack: dict[str, float] = {}
    defense: dict[str, float] = {}
    for team in teams:
        a_vals: list[tuple[float, float]] = []
        d_vals: list[tuple[float, float]] = []
        if team in home_att.index:
            w_home = float(df[df["home_team"] == team]["_w"].sum())
            a_vals.append((home_att[team], w_home))
            d_vals.append((home_def[team], w_home))
        if team in away_att.index:
            w_away = float(df[df["away_team"] == team]["_w"].sum())
            a_vals.append((away_att[team], w_away))
            d_vals.append((away_def[team], w_away))
        attack[team] = _wmean(a_vals, 1.0)
        defense[team] = _wmean(d_vals, 1.0)

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


@dataclass
class XgCalibration:
    """P2.1: Dados de xG recente para calibrar λ (últimos N jogos via Sofascore).

    O xG captura a qualidade das chances criadas, enquanto gols reais incluem
    sorte/azar. Ao blendar xG com o λ baseado em gols, reduzimos variância.
    """

    home_xg_for: float | None = None  # xG médio a favor da casa (últimos jogos)
    home_xg_against: float | None = None  # xG médio contra a casa
    away_xg_for: float | None = None  # xG médio a favor do visitante
    away_xg_against: float | None = None  # xG médio contra o visitante


# Peso do xG na calibração do λ (0.0 = só gols reais, 1.0 = só xG)
_XG_BLEND_WEIGHT = 0.35


def _apply_xg_calibration(
    lambda_home: float,
    lambda_away: float,
    xg: XgCalibration | None,
) -> tuple[float, float]:
    """P2.1: Ajusta λ com base no xG recente, blendando com o valor puro de gols.

    Se xG_for do time é maior que o λ calculado por gols → time cria mais chances
    do que converte → λ sobe (boa fase ofensiva, azar nos chutes).
    Se xG_for é menor → time converte mais do que cria → λ desce (sorte recente).
    """
    if xg is None:
        return lambda_home, lambda_away

    w = _XG_BLEND_WEIGHT

    if xg.home_xg_for is not None and xg.home_xg_for > 0:
        lambda_home = lambda_home * (1 - w) + xg.home_xg_for * w

    if xg.away_xg_for is not None and xg.away_xg_for > 0:
        lambda_away = lambda_away * (1 - w) + xg.away_xg_for * w

    # Clamp mínimo
    lambda_home = max(0.3, lambda_home)
    lambda_away = max(0.3, lambda_away)

    return lambda_home, lambda_away


def expected_lambdas(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
    xg_calibration: XgCalibration | None = None,
) -> tuple[float, float]:
    """Calcula λ esperado para casa e visitante.

    P2.1: Se xg_calibration for fornecido, ajusta o λ com blend xG + gols reais.
    """
    history = _history_until(fixtures_df, before_date)
    ref = _reference_season(history)
    attack, defense, league_avg = _team_attack_defense(history, ref_season=ref)

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

    # P2.1: Calibração xG
    lam_home, lam_away = _apply_xg_calibration(lam_home, lam_away, xg_calibration)

    return lam_home, lam_away


def goal_model_factors(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    features: WcMatchFeatures | None = None,
    before_date: datetime | None = None,
    rho: float = 0.0,
    xg_calibration: XgCalibration | None = None,
) -> GoalModelFactors:
    """Calcula fatores do modelo de gols (ataque, defesa, λ, etc.).

    P2.1: Se xg_calibration for fornecido, ajusta o λ final com blend xG.
    """
    history = _history_until(fixtures_df, before_date)
    ref = _reference_season(history)
    attack, defense, league_avg = _team_attack_defense(history, ref_season=ref)

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

    # P2.1: Calibração xG
    lam_home, lam_away = _apply_xg_calibration(lam_home, lam_away, xg_calibration)

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
