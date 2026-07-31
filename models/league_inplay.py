"""Simulação in-play para jogos de clubes (λ via Dixon-Coles de liga)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings
from models.league_dixon_coles import (
    get_league_dixon_coles_model,
    league_expected_lambdas,
    load_league_fixtures,
    predict_league_probs,
)
from models.wc_inplay import InPlayResult, simulate_inplay

_DEFAULT_MARKET_LAMBDAS = (1.35, 1.15)


def _load_market_prior_weight() -> float:
    path = Path("data/bolao/league_hyperparams.json")
    if not path.exists():
        return 0.65
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return float(raw.get("inplay_market_prior_weight", 0.65))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return 0.65


def _lambdas_from_market(
    market_probs: tuple[float, float, float] | None,
    *,
    match_minutes: int = 90,
) -> tuple[float, float]:
    if market_probs is None:
        return _DEFAULT_MARKET_LAMBDAS
    mp_h, mp_d, mp_a = market_probs
    if mp_h <= 0 or mp_d <= 0 or mp_a <= 0:
        return _DEFAULT_MARKET_LAMBDAS
    from models.wc_market_shrinkage import market_prob_to_lambda

    return market_prob_to_lambda(mp_h, mp_d, mp_a, match_minutes=match_minutes)


def inplay_for_market_prior_match(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    before_date: datetime | None = None,
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    match_minutes: int = 90,
    n_simulations: int | None = None,
    momentum_events: list[dict] | None = None,
    home_corners: int = 0,
    away_corners: int = 0,
    market_probs: tuple[float, float, float] | None = None,
    halftime_stats: Any | None = None,
    live_stats: dict[str, float] | None = None,
    live_timeline: list[dict[str, Any]] | None = None,
    match_context: dict[str, Any] | None = None,
    live_research: dict[str, Any] | None = None,
    fast: bool = False,
) -> InPlayResult:
    """In-play para ligas sem fixtures: λ neutro + shrinkage forte no mercado."""
    lam_home, lam_away = _lambdas_from_market(market_probs, match_minutes=match_minutes)
    # Sem histórico: reforça prior de mercado via λ inicial próximo do implícito
    _ = _load_market_prior_weight()
    seed = hash((home_team, away_team, home_score, away_score, minute, "market")) % (2**32)
    return simulate_inplay(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        lambda_full_home=lam_home,
        lambda_full_away=lam_away,
        match_minutes=match_minutes,
        ht_home_score=ht_home_score,
        ht_away_score=ht_away_score,
        rho=0.0,
        n_simulations=n_simulations or (settings.inplay_fast_mc_simulations if fast else None),
        random_seed=seed,
        momentum_events=momentum_events,
        home_corners=home_corners,
        away_corners=away_corners,
        market_probs=market_probs,
        halftime_stats=halftime_stats,
        live_stats=live_stats,
        live_timeline=live_timeline,
        match_context=match_context,
        live_research=live_research,
    )


def inplay_for_club_match(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    competition: str = "Brasileirão",
    before_date: datetime | None = None,
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    match_minutes: int = 90,
    n_simulations: int | None = None,
    momentum_events: list[dict] | None = None,
    home_corners: int = 0,
    away_corners: int = 0,
    market_probs: tuple[float, float, float] | None = None,
    halftime_stats: Any | None = None,
    live_stats: dict[str, float] | None = None,
    live_timeline: list[dict[str, Any]] | None = None,
    match_context: dict[str, Any] | None = None,
    live_research: dict[str, Any] | None = None,
    fast: bool = False,
) -> InPlayResult:
    """Monte Carlo in-play com λ pré-jogo calibrado para campeonato de clubes."""
    fixtures = load_league_fixtures(competition)
    model = get_league_dixon_coles_model(fixtures)
    rho = float(model.rho) if model else 0.0

    history = fixtures if not fixtures.empty else _empty_fixtures()
    lam_home, lam_away = league_expected_lambdas(
        history,
        home_team,
        away_team,
        before_date=before_date,
        is_neutral=False,
    )

    seed = hash((home_team, away_team, home_score, away_score, minute)) % (2**32)
    return simulate_inplay(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        lambda_full_home=lam_home,
        lambda_full_away=lam_away,
        match_minutes=match_minutes,
        ht_home_score=ht_home_score,
        ht_away_score=ht_away_score,
        rho=rho,
        n_simulations=n_simulations or (settings.inplay_fast_mc_simulations if fast else None),
        random_seed=seed,
        momentum_events=momentum_events,
        home_corners=home_corners,
        away_corners=away_corners,
        market_probs=market_probs,
        halftime_stats=halftime_stats,
        live_stats=live_stats,
        live_timeline=live_timeline,
        match_context=match_context,
        live_research=live_research,
    )


def league_pregame_probs(
    home_team: str,
    away_team: str,
    *,
    competition: str = "Brasileirão",
    before_date: datetime | None = None,
) -> dict[str, float] | None:
    return predict_league_probs(
        home_team,
        away_team,
        competition,
        before_date=before_date,
        is_neutral=False,
    )


def _empty_fixtures():
    import pandas as pd

    return pd.DataFrame(
        columns=[
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "match_date",
            "season",
            "competition",
        ]
    )


__all__ = ["inplay_for_club_match", "inplay_for_market_prior_match", "league_pregame_probs"]
