"""Testes filtros de sanidade beisebol."""
from __future__ import annotations

from models.baseball_aporte_sanity import (
    block_baseball_aporte,
    classify_baseball_line_tier,
    dedupe_correlated_baseball_aportes,
    filter_sane_baseball_aportes,
)
from models.baseball_inplay import simulate_baseball_inplay


def _inplay_pre_game():
    return simulate_baseball_inplay(
        home_team="Albuquerque Isotopes",
        away_team="Sacramento River Cats",
        home_score=0,
        away_score=0,
        inning=1,
        moneyline_odds={"1": 1.90, "2": 1.90},
        total_runs_odds={"9.5": {"over": 1.90, "under": 1.90}},
        team_totals={
            "home": {
                "12.5": {"over": 4.0, "under": 1.20},
                "13.5": {"over": 2.95, "under": 1.35},
            }
        },
        n_simulations=2000,
        random_seed=99,
    )


def test_prior_ignores_extreme_total_line_for_lambda():
    """Over 22.5 no feed não deve inflar o prior de λ."""
    result = simulate_baseball_inplay(
        home_team="A",
        away_team="B",
        home_score=0,
        away_score=0,
        inning=1,
        total_runs_odds={
            "9.5": {"over": 1.90, "under": 1.90},
            "22.5": {"over": 2.50, "under": 1.45},
        },
        n_simulations=1500,
        random_seed=1,
    )
    assert result.market_total_line == 9.5
    assert result.expected_total < 14.0


def test_block_team_total_over_far_from_projection():
    inplay = _inplay_pre_game()
    blocked, reason = block_baseball_aporte(
        {
            "market": "team_total_runs",
            "outcome": "home_over_12_5",
            "market_odd": 4.0,
            "model_prob": 0.35,
            "action": "apostar",
        },
        inplay=inplay,
    )
    assert blocked is True
    assert reason is not None


def test_block_highest_inning_long_shot():
    inplay = _inplay_pre_game()
    blocked, _ = block_baseball_aporte(
        {
            "market": "highest_inning",
            "outcome": "highest_inning_9",
            "market_odd": 35.0,
            "model_prob": 0.15,
            "action": "apostar",
        },
        inplay=inplay,
    )
    assert blocked is True


def test_dedupe_keeps_one_team_over():
    aportes = [
        {"market": "team_total_runs", "outcome": "home_over_12_5", "expected_value": 0.2},
        {"market": "team_total_runs", "outcome": "home_over_13_5", "expected_value": 0.05},
        {"market": "moneyline", "outcome": "1", "expected_value": 0.1},
    ]
    out = dedupe_correlated_baseball_aportes(aportes)
    home_overs = [a for a in out if a["market"] == "team_total_runs"]
    assert len(home_overs) == 1
    assert home_overs[0]["outcome"] == "home_over_12_5"


def test_filter_sane_removes_isotopes_style_bets():
    inplay = _inplay_pre_game()
    raw = [
        {
            "market": "team_total_runs",
            "outcome": "home_over_12_5",
            "label": "Over 12.5",
            "market_odd": 4.0,
            "model_prob": 0.30,
            "implied_prob": 0.25,
            "expected_value": 0.20,
            "edge_pp": 5.0,
            "kelly_quarter": 0.02,
            "suggested_stake_pct": 0.01,
            "action": "apostar",
        },
        {
            "market": "total_runs",
            "outcome": "over_22_5",
            "label": "Over 22.5",
            "market_odd": 2.5,
            "model_prob": 0.45,
            "implied_prob": 0.40,
            "expected_value": 0.12,
            "edge_pp": 5.0,
            "kelly_quarter": 0.01,
            "suggested_stake_pct": 0.01,
            "action": "apostar",
        },
    ]
    kept, warnings = filter_sane_baseball_aportes(raw, inplay=inplay)
    assert len(kept) == 0
    assert warnings


def test_classify_total_runs_alternative_line():
    inplay = _inplay_pre_game()
    tier = classify_baseball_line_tier(
        {"market": "total_runs", "outcome": "over_10_5", "market_odd": 2.1},
        inplay=inplay,
    )
    assert tier == "alternative"


def test_classify_total_runs_extreme_line():
    inplay = _inplay_pre_game()
    tier = classify_baseball_line_tier(
        {"market": "total_runs", "outcome": "over_14_5", "market_odd": 3.0},
        inplay=inplay,
    )
    assert tier == "extreme"


def test_classify_highest_inning_alternative():
    inplay = _inplay_pre_game()
    tier = classify_baseball_line_tier(
        {"market": "highest_inning", "outcome": "highest_inning_7", "market_odd": 5.0},
        inplay=inplay,
    )
    assert tier == "alternative"
