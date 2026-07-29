"""Testes de mercados derivados (dupla chance, DNB, faltas, escanteios)."""
from __future__ import annotations

from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
from models.wc_bet_advice import _aporte_candidates, _market_odd, _prob_from_inplay
from models.wc_derived_markets import (
    double_chance_probs,
    draw_no_bet_probs,
    enrich_inplay_derived_probs,
    foul_line_probs,
    team_corner_line_probs,
)
from models.wc_inplay import simulate_inplay


def test_double_chance_from_h2h():
    dc = double_chance_probs(0.50, 0.30, 0.20)
    assert abs(dc["1X"] - 0.80) < 1e-6
    assert abs(dc["X2"] - 0.50) < 1e-6
    assert abs(dc["12"] - 0.70) < 1e-6


def test_draw_no_bet_renormalizes_without_draw():
    dnb = draw_no_bet_probs(0.50, 0.30, 0.20)
    assert abs(dnb["home"] - 0.50 / 0.70) < 1e-4
    assert abs(dnb["away"] - 0.20 / 0.70) < 1e-4


def test_enrich_inplay_derived_probs():
    base = {
        "prob_final_home": 0.45,
        "prob_final_draw": 0.30,
        "prob_final_away": 0.25,
        "prob_sh_home": 0.40,
        "prob_sh_draw": 0.35,
        "prob_sh_away": 0.25,
    }
    enriched = enrich_inplay_derived_probs(base)
    assert enriched["ft_double_chance"]["1X"] == 0.75
    assert enriched["2h_draw_no_bet"]["home"] > enriched["2h_draw_no_bet"]["away"]


def test_foul_line_probs_poisson():
    probs = foul_line_probs(24.0, (20.5, 25.5))
    assert probs["over_20_5"] > probs["over_25_5"]
    assert abs(probs["over_20_5"] + probs["under_20_5"] - 1.0) < 1e-6


def test_team_corner_line_probs_respects_observed():
    probs = team_corner_line_probs(
        lambda_home_ft=5.0,
        lambda_away_ft=4.0,
        observed_home=6,
        observed_away=2,
        home_lines=(5.5,),
        away_lines=(3.5,),
    )
    assert probs["home_over_5_5"] == 1.0
    assert 0.0 < probs["away_over_3_5"] < 1.0


def test_handicap_3way_in_simulate_inplay():
    result = simulate_inplay(
        home_team="Brasil",
        away_team="Egito",
        home_score=0,
        away_score=0,
        minute=10,
        lambda_full_home=1.4,
        lambda_full_away=0.9,
        n_simulations=8000,
        random_seed=42,
    )
    probs = result.ft_handicap_3way_probs
    assert probs
    assert any(k.startswith("home_") for k in probs)
    assert any(k.startswith("draw_") for k in probs)
    assert any(k.startswith("away_") for k in probs)
    # Por linha, soma ≈ 1
    for line in ("m1", "0", "p1"):
        total = sum(probs.get(f"{side}_{line}", 0) for side in ("home", "draw", "away"))
        if total > 0:
            assert abs(total - 1.0) < 0.05


def test_derived_markets_in_aporte_candidates():
    inplay = simulate_inplay(
        home_team="Casa",
        away_team="Fora",
        home_score=0,
        away_score=0,
        minute=20,
        lambda_full_home=1.2,
        lambda_full_away=1.0,
        n_simulations=3000,
        random_seed=7,
    ).to_dict()
    inplay.update(enrich_inplay_derived_probs(inplay))
    inplay["foul_line_probs"] = foul_line_probs(23.0, (20.5,))
    inplay["corners_h2h_probs"] = {"1": 0.45, "X": 0.20, "2": 0.35}
    inplay["corners_projection"] = {
        "prob_home_more_corners": 0.45,
        "prob_draw_corners": 0.20,
        "prob_away_more_corners": 0.35,
        "expected_ft_home": 5.0,
        "expected_ft_away": 4.0,
    }
    inplay["team_corner_line_probs"] = team_corner_line_probs(
        lambda_home_ft=5.0,
        lambda_away_ft=4.0,
        home_lines=(4.5,),
        away_lines=(3.5,),
    )

    snap = SuperbetEventSnapshot(
        event_id=1,
        home_team="Casa",
        away_team="Fora",
        event_name="Casa · Fora",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=0,
            away_score=0,
            minute=20,
            stoppage_time=None,
            home_corners=2,
            away_corners=1,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="1T",
            status="live",
        ),
        h2h_odds={"1": 2.0, "X": 3.2, "2": 3.8},
        h2h_implied={"1": 0.45, "X": 0.28, "2": 0.27},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        double_chance_odds={"1X": 1.35, "X2": 1.55, "12": 1.25},
        draw_no_bet_odds={"home": 1.45, "away": 2.65},
        fouls={"20.5": {"Mais de 20.5": 1.85, "Menos de 20.5": 1.95}},
        team_corners={"home": {"4.5": {"Mais de 4.5": 1.90}}, "away": {"3.5": {"Mais de 3.5": 1.80}}},
        corners_h2h_odds={"1": 1.95, "X": 7.0, "2": 2.10},
        handicap_3way={"m1": {"home": 2.5, "draw": 3.4, "away": 2.2}},
    )

    markets = {m for m, _, _, _, _, _ in _aporte_candidates(inplay, snap, minute=20)}
    assert "dc_1x" in markets
    assert "dnb_home" in markets
    assert "fouls_over_20_5" in markets
    assert "corners_h2h" in markets
    assert "home_corners_over_4_5" in markets
    assert "ft_hcap3_home_m1" in markets

    assert _prob_from_inplay(inplay, "dc_1x", "yes") is not None
    assert _market_odd(snap, "dc_1x", "yes") == 1.35
    assert _market_odd(snap, "fouls_over_20_5", "yes") == 1.85
