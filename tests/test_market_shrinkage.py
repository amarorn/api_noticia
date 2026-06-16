"""Testes de market shrinkage (Fase 1c)."""
from models.wc_market_shrinkage import (
    compute_alpha,
    market_prob_to_lambda,
    market_probs_from_h2h_implied,
    shrink_lambda,
)


def test_alpha_schedule_decreases():
    assert compute_alpha(0) == 0.70
    assert compute_alpha(40) == 0.50
    assert compute_alpha(80) == 0.30
    assert compute_alpha(90) == 0.30


def test_market_probs_from_h2h_implied_normalizes():
    probs = market_probs_from_h2h_implied({"1": 0.45, "X": 0.30, "2": 0.30})
    assert probs is not None
    assert abs(sum(probs) - 1.0) < 1e-6


def test_shrink_lambda_moves_toward_market_at_kickoff():
    lam_mkt_h, lam_mkt_a = market_prob_to_lambda(0.33, 0.34, 0.33)
    result = shrink_lambda(
        lambda_model_home=1.5,
        lambda_model_away=1.0,
        market_prob_home=0.33,
        market_prob_draw=0.34,
        market_prob_away=0.33,
        minute=0,
    )
    assert result.alpha_used == 0.70
    assert abs(result.lambda_shrunk_home - lam_mkt_h) < abs(1.5 - lam_mkt_h)
    assert abs(result.lambda_shrunk_away - lam_mkt_a) < abs(1.0 - lam_mkt_a)


def test_shrink_lambda_balanced_odds_near_model_at_late_game():
    result = shrink_lambda(
        lambda_model_home=1.4,
        lambda_model_away=1.1,
        market_prob_home=0.33,
        market_prob_draw=0.34,
        market_prob_away=0.33,
        minute=85,
    )
    assert result.alpha_used == 0.30
    assert abs(result.lambda_shrunk_home - 1.4) < 0.15
    assert abs(result.lambda_shrunk_away - 1.1) < 0.15
