from models.wc_bet_advice import (
    UserBetInput,
    advise_cashout,
    advise_aportes,
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
