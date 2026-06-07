from models.wc_bet_advice import UserBetInput, advise_cashout, advise_aportes, build_bet_advice_report


def _inplay_1x1_late():
    return {
        "current_score": "1x1",
        "prob_final_home": 0.22,
        "prob_final_draw": 0.66,
        "prob_final_away": 0.12,
        "prob_next_goal_home": 0.23,
        "prob_next_goal_away": 0.15,
        "prob_no_more_goals": 0.62,
        "btts_final": 1.0,
        "final_line_probs": {"over_2_5": 0.38, "under_2_5": 0.62},
        "combo_markets": {"btts_and_over_3_5": 0.36},
    }


def test_cashout_when_ev_turns_negative():
    bet = UserBetInput(market="h2h", outcome="1", stake=100, odds_placed=2.2)
    advice = advise_cashout(bet, _inplay_1x1_late(), minute=85)
    assert advice.action in {"cashout", "cashout_parcial", "aguardar"}
    assert advice.remaining_ev < 0.5


def test_cashout_hold_when_strong_favorite():
    inplay = {
        "prob_final_home": 0.85,
        "prob_final_draw": 0.10,
        "prob_final_away": 0.05,
        "final_line_probs": {},
        "combo_markets": {},
        "btts_final": 0.5,
    }
    bet = UserBetInput(market="h2h", outcome="1", stake=50, odds_placed=1.5)
    advice = advise_cashout(bet, inplay, minute=70)
    assert advice.action == "manter"
    assert advice.remaining_ev > 0


def test_build_report_includes_aportes_list():
    report = build_bet_advice_report(
        home_team="Brasil",
        away_team="Egito",
        inplay=_inplay_1x1_late(),
        snapshot=None,
        user_bet=UserBetInput(market="h2h", outcome="1", stake=100, odds_placed=2.0),
        minute=17,
    )
    assert report["cashout"] is not None
    assert "action" in report["cashout"]
    assert isinstance(report["aportes"], list)
