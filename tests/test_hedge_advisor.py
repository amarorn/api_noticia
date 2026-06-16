"""Testes do módulo de Hedge Advisor (models/wc_hedge_advisor.py)."""
import pytest

from models.wc_hedge_advisor import (
    advise_open_bets,
    advise_single_bet,
    _get_prob_for_outcome,
    _calculate_hedge,
)


# ── Fixtures de teste ──

INPLAY_2x0_MIN83 = {
    "prob_final_home": 0.997,
    "prob_final_draw": 0.002,
    "prob_final_away": 0.001,
    "final_line_probs": {
        "over_2_5": 0.18,
        "under_2_5": 0.82,
        "over_3_5": 0.03,
        "under_3_5": 0.97,
    },
    "btts_final": 0.04,
    "prob_next_goal_home": 0.15,
    "prob_next_goal_away": 0.04,
    "prob_no_more_goals": 0.81,
}

INPLAY_0x0_MIN30 = {
    "prob_final_home": 0.42,
    "prob_final_draw": 0.28,
    "prob_final_away": 0.30,
    "final_line_probs": {
        "over_2_5": 0.55,
        "under_2_5": 0.45,
        "over_3_5": 0.30,
        "under_3_5": 0.70,
    },
    "btts_final": 0.50,
    "prob_next_goal_home": 0.35,
    "prob_next_goal_away": 0.28,
    "prob_no_more_goals": 0.37,
}


BET_OVER_35 = {
    "id": "bet_1",
    "event_name": "9 De Octubre — Vinotinto",
    "home_team": "9 De Octubre",
    "away_team": "Vinotinto",
    "picks": [{"market": "totals_3.5", "outcome": "over"}],
    "stake": 20.0,
    "odds_placed": 2.85,
    "potential_return": 57.0,
    "status": "open",
}

BET_AWAY_WIN = {
    "id": "bet_2",
    "event_name": "9 De Octubre — Vinotinto",
    "home_team": "9 De Octubre",
    "away_team": "Vinotinto",
    "picks": [{"market": "h2h", "outcome": "away"}],
    "stake": 29.0,
    "odds_placed": 30.0,
    "potential_return": 870.0,
    "status": "open",
}

BET_HOME_WIN = {
    "id": "bet_3",
    "event_name": "Time A — Time B",
    "home_team": "Time A",
    "away_team": "Time B",
    "picks": [{"market": "h2h", "outcome": "home"}],
    "stake": 25.0,
    "odds_placed": 2.50,
    "potential_return": 62.5,
    "status": "open",
}


class TestGetProbForOutcome:
    """Testa extração de probabilidades do inplay dict."""

    def test_h2h_home(self):
        assert _get_prob_for_outcome(INPLAY_2x0_MIN83, "h2h", "home") == 0.997

    def test_h2h_away(self):
        assert _get_prob_for_outcome(INPLAY_2x0_MIN83, "h2h", "away") == 0.001

    def test_totals_over_35(self):
        assert _get_prob_for_outcome(INPLAY_2x0_MIN83, "totals_3.5", "over") == 0.03

    def test_btts_yes(self):
        assert _get_prob_for_outcome(INPLAY_2x0_MIN83, "btts", "yes") == 0.04

    def test_unknown_market(self):
        assert _get_prob_for_outcome(INPLAY_2x0_MIN83, "corners", "over") is None


class TestCalculateHedge:
    """Testa cálculo matemático de hedge."""

    def test_basic_hedge(self):
        # Apostei R$20 @ 3.0, quero proteger com odd oposta de 2.0
        hedge = _calculate_hedge(20.0, 3.0, 2.0)
        assert hedge is not None
        # stake_hedge = 20 / (2.0 - 1) = 20
        assert hedge.stake_suggested == 20.0
        # Se original ganha: 60 - 20 - 20 = 20
        assert hedge.net_if_original_wins == 20.0
        # Se hedge ganha: 20×2 - 20 - 20 = 0
        assert hedge.net_if_hedge_wins == 0.0

    def test_low_odds_hedge(self):
        # Odd de hedge = 1.1 → stake muito alto (200), lucro se original ganha
        # seria 60 - 20 - 200 = -160 → negativo → hedge não faz sentido → None
        hedge = _calculate_hedge(20.0, 3.0, 1.1)
        assert hedge is None  # stake de hedge alto demais anula lucro

    def test_invalid_odds(self):
        assert _calculate_hedge(20.0, 3.0, 1.0) is None
        assert _calculate_hedge(20.0, 3.0, 0.5) is None


class TestAdviseSingleBet:
    """Testa aconselhamento de aposta individual."""

    def test_over35_at_min83_2x0_should_cashout(self):
        """Over 3.5 com P=3% → cash-out urgente."""
        advice = advise_single_bet(BET_OVER_35, INPLAY_2x0_MIN83, minute=83)
        assert advice.action == "cashout"
        assert advice.urgency == "critical"
        assert advice.prob_current == pytest.approx(0.03, abs=0.01)
        assert advice.ev_remaining < -0.5

    def test_away_win_at_min83_2x0_should_cashout(self):
        """Vinotinto vence com P=0.1% → cash-out urgente."""
        advice = advise_single_bet(BET_AWAY_WIN, INPLAY_2x0_MIN83, minute=83)
        assert advice.action == "cashout"
        assert advice.urgency == "critical"
        assert advice.ev_remaining < -0.9

    def test_home_win_at_0x0_min30_should_hold(self):
        """Casa vence com P=42% a odd 2.50 → EV +5% → manter."""
        advice = advise_single_bet(BET_HOME_WIN, INPLAY_0x0_MIN30, minute=30)
        assert advice.action == "hold"
        assert advice.ev_remaining > 0.0

    def test_end_of_game_with_marginal_prob(self):
        """Fim de jogo (min 88) com P < 50% → cash-out."""
        # Mesmo se EV positivo, fim de jogo com P baixa → cash-out
        inplay = {**INPLAY_0x0_MIN30, "prob_final_home": 0.40}
        advice = advise_single_bet(BET_HOME_WIN, inplay, minute=88)
        assert advice.action == "cashout"
        assert advice.urgency == "high"


class TestAdviseOpenBets:
    """Testa relatório consolidado de múltiplas apostas."""

    def test_all_bets_critical(self):
        """Cenário 2x0 min 83 → todas as apostas em risco."""
        bets = [BET_OVER_35, BET_AWAY_WIN]
        report = advise_open_bets(
            bets, INPLAY_2x0_MIN83,
            minute=83, home_team="9 De Octubre", away_team="Vinotinto",
        )
        assert report.overall_action == "cashout"
        assert len(report.advices) == 2
        assert all(a.urgency == "critical" for a in report.advices)

    def test_deduplication(self):
        """Apostas duplicadas (mesma stake/odds/market) devem ser deduplicadas."""
        bets = [BET_OVER_35, BET_OVER_35.copy(), BET_OVER_35.copy()]
        report = advise_open_bets(
            bets, INPLAY_2x0_MIN83,
            minute=83, home_team="9 De Octubre", away_team="Vinotinto",
        )
        assert len(report.advices) == 1

    def test_no_bets_for_event(self):
        """Sem apostas do evento → relatório vazio."""
        report = advise_open_bets(
            [BET_HOME_WIN],  # bet de outro evento
            INPLAY_2x0_MIN83,
            minute=83, home_team="9 De Octubre", away_team="Vinotinto",
        )
        assert len(report.advices) == 0

    def test_mixed_bets_hold_and_cashout(self):
        """Mistura de apostas boas e ruins."""
        good_bet = {
            **BET_HOME_WIN,
            "event_name": "9 De Octubre — Vinotinto",
            "home_team": "9 De Octubre",
            "away_team": "Vinotinto",
            "picks": [{"market": "h2h", "outcome": "home"}],
        }
        report = advise_open_bets(
            [good_bet, BET_AWAY_WIN],
            INPLAY_2x0_MIN83,
            minute=83, home_team="9 De Octubre", away_team="Vinotinto",
        )
        actions = {a.action for a in report.advices}
        # Home win com P=99.7% → hold; Away win com P=0.1% → cashout
        assert "hold" in actions or "cashout" in actions
