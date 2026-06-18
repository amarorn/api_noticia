from models.wc_bet_advice import (
    UserBetInput,
    CashoutAdvice,
    advise_cashout,
    advise_aportes,
    apply_trend_to_cashout,
    build_bet_advice_report,
    _prob_from_inplay,
    _market_odd,
)
from models.wc_inplay import simulate_inplay
from ingest.superbet.parser import parse_superbet_event
import json
from pathlib import Path

HALF_FIXTURE = Path(__file__).parent / "fixtures" / "superbet_mexico_sa_half.json"


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


def test_half_market_prob_and_odd_mapping():
    raw = json.loads(HALF_FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = simulate_inplay(
        home_team=snap.home_team,
        away_team=snap.away_team,
        home_score=0,
        away_score=0,
        minute=12,
        lambda_full_home=1.3,
        lambda_full_away=1.0,
        n_simulations=5000,
        random_seed=17,
    ).to_dict()

    prob_cs = _prob_from_inplay(inplay, "1h_cs_1_0", "yes")
    assert prob_cs is not None
    assert 0.0 < prob_cs < 1.0

    odd_cs = _market_odd(snap, "1h_cs_1_0", "yes")
    assert odd_cs == 4.50

    prob_exact = _prob_from_inplay(inplay, "1h_exact_1", "yes")
    assert prob_exact is not None

    prob_hcap = _prob_from_inplay(inplay, "1h_hcap_home_m0_5", "yes")
    assert prob_hcap is not None
    assert _market_odd(snap, "1h_hcap_home_m0_5", "yes") == 1.90


def test_1h_totals_odd_respects_over_under_outcome():
    """1T under não pode herdar a odd do over (ex.: menos 1.5 @ 15 quando é o mais)."""
    raw = json.loads(HALF_FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    over_odd = _market_odd(snap, "1h_over_1_5", "yes")
    under_odd = _market_odd(snap, "1h_over_1_5", "no")
    assert over_odd is not None
    assert under_odd is not None
    assert over_odd != under_odd
    assert _market_odd(snap, "1h_over_0_5", "yes") != _market_odd(snap, "1h_over_0_5", "no")


def test_handicap_odd_requires_exact_book_button():
    """Não usar linha espelhada: Argentina +1.5 inexistente ≠ odd do -1.5."""
    from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState

    snap = SuperbetEventSnapshot(
        event_id=1,
        home_team="Argentina",
        away_team="Argélia",
        event_name="Argentina - Argélia",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=1,
            away_score=0,
            minute=55,
            stoppage_time=None,
            home_corners=0,
            away_corners=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=1,
            ht_away_score=0,
            period_label="2H",
            status="live",
        ),
        h2h_odds={"1": 1.5, "X": 4.0, "2": 6.0},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={},
        team_shots_on_target={},
        half_markets={
            "ft": {
                "handicap": {
                    "m1_5": {"home": 1.97},
                    "p0_5": {"home": 1.004},
                    "p1_5": {"away": 1.80},
                },
            },
        },
        handicap_odds={},
        handicap_implied={},
        raw_market_count=1,
        captured_at="2026-06-16T00:00:00Z",
    )
    assert _market_odd(snap, "ft_hcap_away_p1_5", "yes") == 1.80
    assert _market_odd(snap, "ft_hcap_home_p1_5", "yes") is None
    assert _market_odd(snap, "ft_hcap_home_m1_5", "yes") == 1.97


def test_advise_aportes_includes_half_markets_when_edge():
    raw = json.loads(HALF_FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = simulate_inplay(
        home_team=snap.home_team,
        away_team=snap.away_team,
        home_score=0,
        away_score=0,
        minute=12,
        lambda_full_home=2.5,
        lambda_full_away=0.4,
        n_simulations=6000,
        random_seed=23,
    ).to_dict()

    aportes = advise_aportes(
        inplay,
        snap,
        bankroll=1000,
        live=True,
        home_team=snap.home_team,
        away_team=snap.away_team,
        minute=12,
        min_edge=-0.5,
    )
    half_markets = {a.market for a in aportes if a.market.startswith(("1h_", "2h_"))}
    assert half_markets


def test_advise_aportes_blocked_after_cutoff():
    inplay = {
        "current_score": "1x1",
        "prob_final_home": 0.40,
        "prob_final_draw": 0.35,
        "prob_final_away": 0.25,
        "final_line_probs": {"over_2_5": 0.55},
        "combo_markets": {},
        "btts_final": 0.6,
    }
    aportes = advise_aportes(inplay, None, live=True, minute=90, confidence_score=1.0)
    assert aportes == []


def _trend_exit_report(urgency: str = "critical", confidence: float = 0.85) -> dict:
    return {
        "position_advice": {
            "action": "exit",
            "urgency": urgency,
            "confidence": confidence,
            "reasoning": "Mercado colapsou contra sua posição nos últimos ticks.",
        }
    }


def test_cashout_trend_upgrades_manter_to_cashout():
    bet = UserBetInput(market="h2h", outcome="X", stake=50, odds_placed=3.5)
    inplay = {
        "prob_final_home": 0.55,
        "prob_final_draw": 0.30,
        "prob_final_away": 0.15,
        "final_line_probs": {},
        "combo_markets": {},
        "btts_final": 0.5,
    }
    advice = advise_cashout(
        bet,
        inplay,
        minute=70,
        trend_report=_trend_exit_report("critical", 0.9),
    )
    assert advice.action == "cashout"
    assert advice.trend_influenced is True
    assert "Copiloto de tendência" in advice.reason


def test_apply_trend_high_urgency_upgrades_aguardar():
    base = CashoutAdvice(
        action="aguardar",
        confidence=0.5,
        reason="Neutro.",
        current_model_prob=0.4,
        placed_implied_prob=0.35,
        remaining_ev=-0.02,
        estimated_fair_cashout=40.0,
        potential_return=100.0,
    )
    merged = apply_trend_to_cashout(base, _trend_exit_report("high", 0.55))
    assert merged.action == "cashout"
    assert merged.trend_influenced is True


def test_apply_trend_medium_urgency_partial_from_manter():
    base = CashoutAdvice(
        action="manter",
        confidence=0.7,
        reason="Valor.",
        current_model_prob=0.6,
        placed_implied_prob=0.45,
        remaining_ev=0.08,
        estimated_fair_cashout=70.0,
        potential_return=110.0,
    )
    merged = apply_trend_to_cashout(base, _trend_exit_report("medium", 0.6))
    assert merged.action == "cashout_parcial"
    assert merged.trend_influenced is True


def test_cashout_trend_disabled(monkeypatch):
    monkeypatch.setattr("config.settings.live_cashout_use_trend", False)
    base = CashoutAdvice(
        action="manter",
        confidence=0.8,
        reason="Valor.",
        current_model_prob=0.7,
        placed_implied_prob=0.5,
        remaining_ev=0.1,
        estimated_fair_cashout=80.0,
        potential_return=120.0,
    )
    merged = apply_trend_to_cashout(base, _trend_exit_report("critical", 0.95))
    assert merged.action == "manter"
    assert merged.trend_influenced is False
