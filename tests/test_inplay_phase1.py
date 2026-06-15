"""Testes de integração Fase 1 in-play."""
from models.wc_inplay import simulate_inplay


def test_probs_sum_to_one_with_phase1_defaults():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=1,
        away_score=0,
        minute=30,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=4000,
        random_seed=21,
    )
    total = r.prob_final_home + r.prob_final_draw + r.prob_final_away
    assert abs(total - 1.0) < 0.02


def test_momentum_on_remaining_changes_probs_not_lambda_full():
    """Momentum em λ_remaining: λ_full reportado reflete Bayesian, não o fator tático."""
    base = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=2,
        away_score=0,
        minute=45,
        lambda_full_home=1.2,
        lambda_full_away=0.8,
        n_simulations=3000,
        random_seed=5,
        use_momentum=False,
    )
    with_momentum = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=2,
        away_score=0,
        minute=45,
        lambda_full_home=1.2,
        lambda_full_away=0.8,
        n_simulations=3000,
        random_seed=5,
        use_momentum=True,
    )
    assert abs(base.lambda_full_home - with_momentum.lambda_full_home) < 0.05
    assert base.prob_final_home != with_momentum.prob_final_home


def test_nhpp_increases_late_remaining_vs_homogeneous():
    nhpp = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=80,
        lambda_full_home=1.5,
        lambda_full_away=1.0,
        n_simulations=1000,
        random_seed=9,
        use_nhpp=True,
        use_momentum=False,
        bayesian_update=False,
    )
    homog = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=80,
        lambda_full_home=1.5,
        lambda_full_away=1.0,
        n_simulations=1000,
        random_seed=9,
        use_nhpp=False,
        use_momentum=False,
        bayesian_update=False,
    )
    assert nhpp.lambda_remaining_home + nhpp.lambda_remaining_away > (
        homog.lambda_remaining_home + homog.lambda_remaining_away
    )


def test_market_shrinkage_pulls_lambda_when_enabled():
    without = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=10,
        lambda_full_home=1.6,
        lambda_full_away=0.7,
        n_simulations=1000,
        random_seed=3,
        use_market_shrinkage=False,
        use_momentum=False,
        bayesian_update=False,
    )
    with_market = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=10,
        lambda_full_home=1.6,
        lambda_full_away=0.7,
        n_simulations=1000,
        random_seed=3,
        market_probs=(0.20, 0.25, 0.55),
        use_market_shrinkage=True,
        use_momentum=False,
        bayesian_update=False,
    )
    assert with_market.lambda_full_away > without.lambda_full_away
