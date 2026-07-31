"""Testes in-play market prior para ligas estrangeiras."""
from __future__ import annotations

from models.league_inplay import inplay_for_market_prior_match


def test_inplay_for_market_prior_match_returns_probs():
    result = inplay_for_market_prior_match(
        home_team="Arsenal",
        away_team="Chelsea",
        home_score=0,
        away_score=0,
        minute=30,
        market_probs=(0.45, 0.28, 0.27),
        n_simulations=500,
        fast=True,
    )
    d = result.to_dict()
    assert 0.0 < d["prob_final_home"] < 1.0
    assert 0.0 < d["prob_final_draw"] < 1.0
    assert 0.0 < d["prob_final_away"] < 1.0
    total = d["prob_final_home"] + d["prob_final_draw"] + d["prob_final_away"]
    assert abs(total - 1.0) < 0.05
