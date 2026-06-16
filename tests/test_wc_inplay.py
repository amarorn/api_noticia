from models.wc_inplay import (
    simulate_inplay,
    bayesian_lambda_update,
    _apply_guaranteed_lines,
    _apply_team_guaranteed_lines,
    _exact_goals_distribution,
    _handicap_probs,
    _score_distribution,
)
import numpy as np


def test_inplay_1x1_at_17_needs_one_for_over25():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=1,
        away_score=1,
        minute=17,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=8000,
        random_seed=7,
    )
    assert r.home_score == 1 and r.away_score == 1
    assert r.final_line_probs["over_2_5"] > r.final_line_probs["over_3_5"]
    assert r.btts_final == 1.0
    assert abs(r.prob_final_home + r.prob_final_draw + r.prob_final_away - 1.0) < 0.02


def test_inplay_late_game_favors_no_more_goals():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=1,
        away_score=1,
        minute=85,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=5000,
        random_seed=3,
    )
    assert r.prob_no_more_goals > 0.5
    assert r.lambda_remaining_home < 0.2


def test_inplay_combo_markets_present():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=1,
        away_score=1,
        minute=17,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=4000,
        random_seed=11,
    )
    assert r.combo_markets["btts_and_over_2_5"] > 0.5
    assert r.combo_markets["ft_draw_and_btts"] > 0.2
    assert "X/X" in r.top_ht_ft or "X/1" in r.top_ht_ft
    assert abs(r.prob_ht_home + r.prob_ht_draw + r.prob_ht_away - 1.0) < 0.02
    assert abs(r.prob_sh_home + r.prob_sh_draw + r.prob_sh_away - 1.0) < 0.02


# --- P0.1: Testes Bayesian lambda update ---


def test_bayesian_lambda_update_no_goals_reduces_lambda():
    """Sem gols observados em metade do jogo, λ posterior deve ser menor que o prior."""
    lam_h = bayesian_lambda_update(
        lambda_prior=1.5,
        goals_observed=0,
        minutes_elapsed=45,
        match_minutes=90,
        prior_weight=3.0,
    )
    lam_a = bayesian_lambda_update(
        lambda_prior=1.0,
        goals_observed=0,
        minutes_elapsed=45,
        match_minutes=90,
        prior_weight=3.0,
    )
    assert lam_h < 1.5
    assert lam_a < 1.0
    # Não deve colapsar — limitar inferior funciona
    assert lam_h >= 1.5 * 0.3
    assert lam_a >= 1.0 * 0.3


def test_bayesian_lambda_update_many_goals_increases_lambda():
    """Muitos gols em pouco tempo → λ posterior sobe."""
    lam_h = bayesian_lambda_update(
        lambda_prior=1.0,
        goals_observed=3,
        minutes_elapsed=30,
        match_minutes=90,
        prior_weight=3.0,
    )
    lam_a = bayesian_lambda_update(
        lambda_prior=0.8,
        goals_observed=2,
        minutes_elapsed=30,
        match_minutes=90,
        prior_weight=3.0,
    )
    assert lam_h > 1.0
    assert lam_a > 0.8
    # Limitar superior funciona
    assert lam_h <= 1.0 * 2.5
    assert lam_a <= 0.8 * 2.5


def test_bayesian_lambda_update_zero_elapsed():
    """Com 0 minutos decorridos, λ = prior (sem informação nova)."""
    lam_h = bayesian_lambda_update(
        lambda_prior=1.5,
        goals_observed=0,
        minutes_elapsed=0,
        match_minutes=90,
        prior_weight=3.0,
    )
    lam_a = bayesian_lambda_update(
        lambda_prior=1.0,
        goals_observed=0,
        minutes_elapsed=0,
        match_minutes=90,
        prior_weight=3.0,
    )
    assert abs(lam_h - 1.5) < 0.01
    assert abs(lam_a - 1.0) < 0.01


# --- P0.2: Testes linhas garantidas ---


def test_guaranteed_lines_over_already_hit():
    """Se placar total = 3, over_2_5 deve ser 1.0 e under_2_5 deve ser 0.0."""
    probs = {
        "over_1_5": 0.85,
        "under_1_5": 0.15,
        "over_2_5": 0.60,
        "under_2_5": 0.40,
        "over_3_5": 0.30,
        "under_3_5": 0.70,
    }
    result = _apply_guaranteed_lines(probs, current_total=3)
    assert result["over_1_5"] == 1.0
    assert result["under_1_5"] == 0.0
    assert result["over_2_5"] == 1.0
    assert result["under_2_5"] == 0.0
    # over_3_5 NÃO é garantido (3 não é > 3.5)
    assert result["over_3_5"] == 0.30
    assert result["under_3_5"] == 0.70


def test_guaranteed_lines_nothing_hit():
    """Placar 0 → nenhum override."""
    probs = {"over_0_5": 0.7, "under_0_5": 0.3, "over_1_5": 0.4, "under_1_5": 0.6}
    result = _apply_guaranteed_lines(probs, current_total=0)
    assert result == probs


def test_team_guaranteed_lines_home_2_goals():
    """Home com 2 gols → home_over_0_5 e home_over_1_5 devem ser 1.0."""
    team_lines = {
        "home_over_0_5": 0.80,
        "home_under_0_5": 0.20,
        "home_over_1_5": 0.50,
        "home_under_1_5": 0.50,
        "home_over_2_5": 0.25,
        "home_under_2_5": 0.75,
        "away_over_0_5": 0.70,
        "away_under_0_5": 0.30,
    }
    result = _apply_team_guaranteed_lines(team_lines, home_score=2, away_score=0)
    assert result["home_over_0_5"] == 1.0
    assert result["home_under_0_5"] == 0.0
    assert result["home_over_1_5"] == 1.0
    assert result["home_under_1_5"] == 0.0
    # home_over_2_5: 2 não é > 2.5
    assert result["home_over_2_5"] == 0.25
    # away com 0 gols — nenhum override
    assert result["away_over_0_5"] == 0.70


def test_simulate_inplay_bayesian_disabled():
    """Com bayesian_update=False, λ não muda."""
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=45,
        lambda_full_home=1.5,
        lambda_full_away=1.0,
        n_simulations=2000,
        random_seed=42,
        bayesian_update=False,
    )
    # Sem Bayesian, lambda_full fica igual ao input
    assert abs(r.lambda_full_home - 1.5) < 0.001
    assert abs(r.lambda_full_away - 1.0) < 0.001


def test_simulate_inplay_guaranteed_over_with_high_score():
    """3×2 aos 70 min → over_2_5 e over_3_5 devem ser 1.0 (total=5)."""
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=3,
        away_score=2,
        minute=70,
        lambda_full_home=1.5,
        lambda_full_away=1.0,
        n_simulations=2000,
        random_seed=99,
    )
    assert r.final_line_probs["over_2_5"] == 1.0
    assert r.final_line_probs["under_2_5"] == 0.0
    assert r.final_line_probs["over_3_5"] == 1.0
    assert r.final_line_probs["under_3_5"] == 0.0
    assert r.final_line_probs["over_4_5"] == 1.0
    assert r.final_line_probs["under_4_5"] == 0.0
    # Team lines
    assert r.team_final_line_probs["home_over_0_5"] == 1.0
    assert r.team_final_line_probs["home_over_1_5"] == 1.0
    assert r.team_final_line_probs["home_over_2_5"] == 1.0
    assert r.team_final_line_probs["away_over_0_5"] == 1.0
    assert r.team_final_line_probs["away_over_1_5"] == 1.0


def test_half_market_probs_present_in_simulation():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=20,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=6000,
        random_seed=13,
    )
    assert r.ht_correct_scores
    assert r.sh_correct_scores
    assert r.ht_exact_totals
    assert r.sh_exact_totals
    assert r.ht_home_exact
    assert r.ht_away_exact
    assert r.sh_home_exact
    assert r.ht_handicap_probs
    assert r.sh_handicap_probs
    d = r.to_dict()
    assert "ht_correct_scores" in d
    assert "sh_exact_totals" in d


def test_exact_goals_distribution_sums_to_one():
    goals = np.array([0, 0, 1, 1, 2, 3, 3, 3, 6, 7])
    dist = _exact_goals_distribution(goals, len(goals), max_goals=5)
    assert abs(sum(dist.values()) - 1.0) < 1e-9
    assert dist["0"] == 0.2
    assert dist["3"] == 0.3
    assert dist["5+"] == 0.2


def test_score_distribution_top_scores():
    h = np.array([1, 1, 0, 2])
    a = np.array([0, 1, 0, 1])
    dist = _score_distribution(h, a, len(h), top_k=5)
    assert dist["1x0"] == 0.25
    assert dist["1x1"] == 0.25
    assert sum(dist.values()) == 1.0


def test_handicap_probs_match_ht_outcome_at_zero_line():
    h = np.array([2, 1, 1, 0, 0])
    a = np.array([0, 1, 0, 0, 1])
    n = len(h)
    probs = _handicap_probs(h, a, n, lines=(0.0,))
    assert abs(probs["home_0"] - np.sum(h > a) / n) < 1e-9
    assert abs(probs["away_0"] - np.sum(h < a) / n) < 1e-9


def test_ht_markets_deterministic_after_halftime():
    """Com intervalo encerrado (1x0 HT), mercados de 1º tempo colapsam no placar HT."""
    r = simulate_inplay(
        home_team="México",
        away_team="África do Sul",
        home_score=1,
        away_score=0,
        minute=55,
        ht_home_score=1,
        ht_away_score=0,
        lambda_full_home=1.2,
        lambda_full_away=0.8,
        n_simulations=4000,
        random_seed=21,
    )
    assert r.ht_correct_scores.get("1x0", 0) == 1.0
    assert r.ht_exact_totals.get("1", 0) == 1.0
    assert r.ht_home_exact.get("1", 0) == 1.0
    assert r.ht_away_exact.get("0", 0) == 1.0
    assert r.ht_handicap_probs.get("home_0", 0) == 1.0
    assert r.ht_handicap_probs.get("away_0", 0) == 0.0
    assert r.ht_line_probs["over_0_5"] == 1.0
    assert r.ht_line_probs["under_0_5"] == 0.0


def test_exact_totals_sum_to_one_in_first_half():
    r = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=10,
        lambda_full_home=1.3,
        lambda_full_away=1.1,
        n_simulations=8000,
        random_seed=5,
    )
    assert abs(sum(r.ht_exact_totals.values()) - 1.0) < 0.02
    assert abs(sum(r.sh_exact_totals.values()) - 1.0) < 0.02
    assert abs(sum(r.ht_home_exact.values()) - 1.0) < 0.02
    assert abs(sum(r.sh_away_exact.values()) - 1.0) < 0.02
