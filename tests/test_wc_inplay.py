from models.wc_inplay import simulate_inplay


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
    assert r.combo_markets["ft_draw_and_btts"] > 0.3
    assert "X/X" in r.top_ht_ft or "X/1" in r.top_ht_ft
    assert abs(r.prob_ht_home + r.prob_ht_draw + r.prob_ht_away - 1.0) < 0.02
