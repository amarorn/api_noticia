"""Dixon-Coles para campeonatos de clubes (Brasileirão e similares).

Reutiliza matriz de scores de ``poisson_wc`` com hiperparâmetros de liga
(home advantage maior, meia-vida temporal curta).
"""
from __future__ import annotations

import json
from pathlib import Path

import math
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from models.poisson_wc import (
    MAX_GOALS,
    _history_until,
    _reference_season,
    _season_weight,
    _wmean,
    score_outcome_probs,
    score_probability,
)
from schemas.models import BolaoLabel

LABELS: tuple[BolaoLabel, ...] = ("1", "X", "2")

# Hiperparâmetros calibrados para futebol doméstico (Série A BR).
LEAGUE_HOME_ADVANTAGE = 0.28
LEAGUE_SEASON_HALF_LIFE = 2.5
RHO_MIN = -0.25
RHO_MAX = 0.05
RHO_STEP = 0.025
MIN_TRAIN_MATCHES = 20

COMPETITION_FIXTURE_KEY = {
    "Brasileirão": "brasileirao",
    "brasileirao": "brasileirao",
    "Brasileirão Série B": "brasileirao_serie_b",
    "Copa Libertadores": "libertadores",
    "libertadores": "libertadores",
}


@dataclass(frozen=True)
class LeagueHyperparams:
    home_advantage: float = LEAGUE_HOME_ADVANTAGE
    season_half_life: float = LEAGUE_SEASON_HALF_LIFE
    rho_min: float = RHO_MIN
    rho_max: float = RHO_MAX
    rho_step: float = RHO_STEP


def _normalized_score_prob(
    home_goals: int,
    away_goals: int,
    lam_home: float,
    lam_away: float,
    rho: float,
) -> float:
    total_mass = sum(
        score_probability(i, j, lam_home, lam_away, rho)
        for i in range(MAX_GOALS + 1)
        for j in range(MAX_GOALS + 1)
    )
    if total_mass <= 0:
        return 1e-12
    return score_probability(home_goals, away_goals, lam_home, lam_away, rho) / total_mass


def _team_attack_defense(
    fixtures_df: pd.DataFrame,
    *,
    ref_season: int | None = None,
    half_life: float = LEAGUE_SEASON_HALF_LIFE,
) -> tuple[dict[str, float], dict[str, float], float]:
    ref = ref_season if ref_season is not None else _reference_season(fixtures_df)
    df = fixtures_df.copy()
    df["_w"] = df["season"].fillna(ref).astype(int).apply(
        lambda s: _season_weight(s, ref, half_life)
    )

    avg_home = float((df["home_score"] * df["_w"]).sum() / max(df["_w"].sum(), 1e-12))
    avg_away = float((df["away_score"] * df["_w"]).sum() / max(df["_w"].sum(), 1e-12))
    league_avg = (avg_home + avg_away) / 2.0

    home_att = df.groupby("home_team").apply(
        lambda g: float((g["home_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12))
        / max(avg_home, 0.5),
        include_groups=False,
    )
    home_def = df.groupby("home_team").apply(
        lambda g: float((g["away_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12))
        / max(avg_away, 0.5),
        include_groups=False,
    )
    away_att = df.groupby("away_team").apply(
        lambda g: float((g["away_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12))
        / max(avg_away, 0.5),
        include_groups=False,
    )
    away_def = df.groupby("away_team").apply(
        lambda g: float((g["home_score"] * g["_w"]).sum() / max(g["_w"].sum(), 1e-12))
        / max(avg_home, 0.5),
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
            a_vals.append((float(home_att[team]), w_home))
            d_vals.append((float(home_def[team]), w_home))
        if team in away_att.index:
            w_away = float(df[df["away_team"] == team]["_w"].sum())
            a_vals.append((float(away_att[team]), w_away))
            d_vals.append((float(away_def[team]), w_away))
        attack[team] = _wmean(a_vals, 1.0)
        defense[team] = _wmean(d_vals, 1.0)

    return attack, defense, league_avg


def league_expected_lambdas(
    fixtures_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    *,
    before_date: datetime | None = None,
    is_neutral: bool = False,
    hyperparams: LeagueHyperparams | None = None,
) -> tuple[float, float]:
    hp = hyperparams or LeagueHyperparams()
    history = _history_until(fixtures_df, before_date)
    ref = _reference_season(history)
    attack, defense, league_avg = _team_attack_defense(
        history,
        ref_season=ref,
        half_life=hp.season_half_life,
    )

    att_h = attack.get(home_team, 1.0)
    att_a = attack.get(away_team, 1.0)
    def_h = defense.get(home_team, 1.0)
    def_a = defense.get(away_team, 1.0)

    home_adv = 0.0 if is_neutral else hp.home_advantage
    lam_home = league_avg * att_h * def_a + home_adv
    lam_away = league_avg * att_a * def_h
    return max(0.3, lam_home), max(0.3, lam_away)


class LeagueDixonColesModel:
    """Poisson + correlação ρ para jogos de clubes em mando de campo."""

    def __init__(self, hyperparams: LeagueHyperparams | None = None) -> None:
        self.hyperparams = hyperparams or LeagueHyperparams()
        self.rho: float = 0.0
        self._fitted = False
        self._fixtures_fingerprint: tuple[int, int] | None = None

    def fit(self, fixtures_df: pd.DataFrame, *, holdout_season: int | None = None) -> dict:
        df = fixtures_df.sort_values("match_date").copy()
        if holdout_season is not None and "season" in df.columns:
            train_df = df[df["season"] < holdout_season]
        else:
            train_df = df

        if len(train_df) < MIN_TRAIN_MATCHES:
            train_df = df

        self.rho = self._estimate_rho(df, train_df)
        self._fitted = True
        self._fixtures_fingerprint = (len(df), int(_reference_season(df)))
        return {"rho": round(self.rho, 4), "train_size": len(train_df)}

    def _estimate_rho(self, fixtures_df: pd.DataFrame, train_df: pd.DataFrame) -> float:
        if len(train_df) < MIN_TRAIN_MATCHES:
            return 0.0

        prepared: list[tuple[int, int, float, float]] = []
        for _, row in train_df.iterrows():
            before = row["match_date"]
            history = fixtures_df[fixtures_df["match_date"] < before]
            if history.empty:
                history = fixtures_df
            is_neutral = bool(row.get("is_neutral", False))
            lam_home, lam_away = league_expected_lambdas(
                history,
                row["home_team"],
                row["away_team"],
                before_date=before,
                is_neutral=is_neutral,
                hyperparams=self.hyperparams,
            )
            prepared.append((int(row["home_score"]), int(row["away_score"]), lam_home, lam_away))

        hp = self.hyperparams
        best_rho = 0.0
        best_ll = float("-inf")
        steps = int(round((hp.rho_max - hp.rho_min) / hp.rho_step))
        for i in range(steps + 1):
            rho = hp.rho_min + i * hp.rho_step
            log_likelihood = 0.0
            for hs, aws, lam_home, lam_away in prepared:
                p = _normalized_score_prob(hs, aws, lam_home, lam_away, rho)
                log_likelihood += math.log(max(p, 1e-12))
            if log_likelihood > best_ll:
                best_ll = log_likelihood
                best_rho = rho
        return best_rho

    def predict_probs(
        self,
        fixtures_df: pd.DataFrame,
        home_team: str,
        away_team: str,
        *,
        before_date: datetime | None = None,
        is_neutral: bool = False,
    ) -> dict[BolaoLabel, float]:
        if not self._fitted:
            self.fit(fixtures_df)

        lam_home, lam_away = league_expected_lambdas(
            fixtures_df,
            home_team,
            away_team,
            before_date=before_date,
            is_neutral=is_neutral,
            hyperparams=self.hyperparams,
        )
        outcome = score_outcome_probs(lam_home, lam_away, rho=self.rho)
        return {
            "1": float(outcome.prob_home),
            "X": float(outcome.prob_draw),
            "2": float(outcome.prob_away),
        }


_MODEL_CACHE: dict[tuple[int, int], LeagueDixonColesModel] = {}


def _fixtures_key(fixtures_df: pd.DataFrame) -> tuple[int, int]:
    if fixtures_df.empty:
        return (0, 0)
    return (len(fixtures_df), int(_reference_season(fixtures_df)))


def load_league_fixtures(competition: str) -> pd.DataFrame:
    from ingest.fixtures.store import load_fixtures

    key = COMPETITION_FIXTURE_KEY.get(competition)
    frames: list[pd.DataFrame] = []
    if key:
        df = load_fixtures(competition=key)
        if not df.empty:
            frames.append(df)
    # Libertadores / clubes BR: enriquecer com Série A
    if key in {"libertadores", "brasileirao"} or competition == "Copa Libertadores":
        br = load_fixtures(competition="brasileirao")
        if not br.empty:
            frames.append(br)
    if not frames:
        all_df = load_fixtures()
        if all_df.empty or "competition" not in all_df.columns:
            return pd.DataFrame()
        return all_df[all_df["competition"] == competition].sort_values("match_date").copy()

    merged = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["match_id"], keep="last")
    return merged.sort_values("match_date").copy()


def load_league_hyperparams() -> LeagueHyperparams:
    path = Path("data/bolao/league_hyperparams.json")
    if not path.exists():
        return LeagueHyperparams()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return LeagueHyperparams(
            home_advantage=float(raw.get("home_advantage", LEAGUE_HOME_ADVANTAGE)),
            season_half_life=float(raw.get("season_half_life", LEAGUE_SEASON_HALF_LIFE)),
            rho_min=float(raw.get("rho_min", RHO_MIN)),
            rho_max=float(raw.get("rho_max", RHO_MAX)),
            rho_step=float(raw.get("rho_step", RHO_STEP)),
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return LeagueHyperparams()


def get_league_dixon_coles_model(fixtures_df: pd.DataFrame) -> LeagueDixonColesModel | None:
    if fixtures_df.empty or len(fixtures_df) < MIN_TRAIN_MATCHES:
        return None
    cache_key = _fixtures_key(fixtures_df)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None:
        return cached
    model = LeagueDixonColesModel(hyperparams=load_league_hyperparams())
    model.fit(fixtures_df)
    _MODEL_CACHE[cache_key] = model
    return model


def predict_league_probs(
    home_team: str,
    away_team: str,
    competition: str,
    *,
    before_date: datetime | None = None,
    is_neutral: bool = False,
) -> dict[BolaoLabel, float] | None:
    fixtures_df = load_league_fixtures(competition)
    model = get_league_dixon_coles_model(fixtures_df)
    if model is None:
        return None
    return model.predict_probs(
        fixtures_df,
        home_team,
        away_team,
        before_date=before_date,
        is_neutral=is_neutral,
    )


def clear_league_model_cache() -> None:
    _MODEL_CACHE.clear()


__all__ = [
    "LeagueDixonColesModel",
    "LeagueHyperparams",
    "clear_league_model_cache",
    "get_league_dixon_coles_model",
    "league_expected_lambdas",
    "load_league_fixtures",
    "load_league_hyperparams",
    "predict_league_probs",
]
