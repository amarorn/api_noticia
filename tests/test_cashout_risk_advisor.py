"""Testes do assessor de risco de cash-out."""
from __future__ import annotations

from models.cashout_risk_advisor import assess_cashout_risk, evaluate_leg_live


def test_under_25_critical_at_two_goals():
    leg = evaluate_leg_live(
        {"market": "over_2_5", "outcome": "no", "label": "Menos de 2.5 gols"},
        home_score=0,
        away_score=2,
        minute=41,
    )
    assert leg.status == "critical"


def test_under_25_lost_at_three_goals():
    leg = evaluate_leg_live(
        {"market": "over_2_5", "outcome": "under", "label": "Menos de 2.5"},
        home_score=0,
        away_score=3,
        minute=50,
    )
    assert leg.status == "lost"


def test_combo_protect_stake_scenario():
    """Cenário do usuário: combo @13, cash-out ~88% stake, under 2.5 crítico."""
    bet = {
        "id": "bet-1",
        "stake": 20.0,
        "odds_placed": 13.0,
        "potential_return": 260.0,
        "cashout_value": 37.53,
        "picks": [
            {"market": "h2h", "outcome": "2", "label": "Vitória visitante"},
            {"market": "over_2_5", "outcome": "no", "label": "Menos de 2.5 gols"},
            {"market": "1h_over_1_5", "outcome": "yes", "label": "Mais de 1.5 1T"},
        ],
    }
    out = assess_cashout_risk(bet, home_score=0, away_score=2, minute=41, ht_home=0, ht_away=2)
    assert out.alert is True
    assert out.action in {"exit_now", "protect_stake", "consider_exit"}
    assert out.cashout_pct_of_stake is not None
    assert out.cashout_pct_of_stake >= 0.5
    assert len(out.critical_legs) >= 1


def test_under_corners_critical_at_limit():
    leg = evaluate_leg_live(
        {"market": "corners_total", "outcome": "under", "target_value": "4.5", "label": "Menos de 4.5 escanteios"},
        home_score=0,
        away_score=0,
        minute=55,
        home_corners=2,
        away_corners=2,
    )
    assert leg.status == "critical"


def test_long_shot_decay_alert():
    bet = {
        "id": "bet-long",
        "stake": 15.0,
        "odds_placed": 19.0,
        "potential_return": 285.0,
        "cashout_value": 2.73,
        "picks": [{"market": "corners_total", "outcome": "under", "target_value": "6.5"}],
    }
    out = assess_cashout_risk(
        bet,
        home_score=0,
        away_score=0,
        minute=60,
        home_corners=3,
        away_corners=2,
    )
    assert out.alert is True
    assert out.action == "consider_exit"
    assert "zerar" in out.message.lower() or "caindo" in out.title.lower()


def test_lock_profit_alert():
    bet = {
        "id": "bet-profit",
        "stake": 25.0,
        "odds_placed": 1.9,
        "potential_return": 47.5,
        "cashout_value": 30.27,
        "picks": [
            {"market": "cards_total", "outcome": "under", "target_value": "2.5"},
            {"market": "handicap", "outcome": "yes", "target_value": "1.5"},
        ],
    }
    out = assess_cashout_risk(
        bet,
        home_score=0,
        away_score=1,
        minute=35,
        home_cards=0,
        away_cards=1,
    )
    assert out.alert is True
    assert "lucro" in out.title.lower() or "lucro" in out.message.lower()


def test_combo_lost_after_third_goal():
    bet = {
        "id": "bet-2",
        "stake": 20.0,
        "potential_return": 260.0,
        "cashout_value": 0.0,
        "picks": [
            {"market": "h2h", "outcome": "2", "label": "Vitória visitante"},
            {"market": "over_2_5", "outcome": "no", "label": "Menos de 2.5 gols"},
        ],
    }
    out = assess_cashout_risk(bet, home_score=0, away_score=3, minute=45)
    assert out.action == "dead"
