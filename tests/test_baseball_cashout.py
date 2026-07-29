"""Testes cash-out beisebol."""
from __future__ import annotations

from models.baseball_cashout import _prob_from_baseball_inplay, advise_baseball_cashout
from models.wc_bet_advice import UserBetInput


def test_prob_from_baseball_moneyline():
    inplay = {"moneyline_probs": {"1": 0.35, "2": 0.65}, "prob_home_win": 0.35}
    assert _prob_from_baseball_inplay(inplay, "moneyline", "1") == 0.35


def test_prob_from_baseball_total():
    inplay = {"total_probs": {"over_8_5": 0.42, "under_8_5": 0.58}}
    assert _prob_from_baseball_inplay(inplay, "total_runs", "over_8_5") == 0.42


def test_advise_cashout_manter_when_value():
    bet = UserBetInput(market="moneyline", outcome="2", stake=50.0, odds_placed=1.5)
    inplay = {
        "moneyline_probs": {"1": 0.20, "2": 0.80},
        "prob_away_win": 0.80,
    }
    advice = advise_baseball_cashout(bet, inplay, inning=4)
    assert advice.action in {"manter", "aguardar"}
    assert advice.remaining_ev > 0
