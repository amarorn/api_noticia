"""Liquidação de tips in-play para post-mortem."""
from __future__ import annotations

from models.inplay_tip_settle import evaluate_inplay_tip


def test_belgium_egypt_2h_away_minus_half_lost():
    assert (
        evaluate_inplay_tip(
            "2h_hcap_away_m0_5",
            "yes",
            home_score=1,
            away_score=1,
            ht_home=0,
            ht_away=1,
        )
        is False
    )


def test_belgium_egypt_1h_away_minus_half_won():
    assert (
        evaluate_inplay_tip(
            "1h_hcap_away_m0_5",
            "yes",
            home_score=1,
            away_score=1,
            ht_home=0,
            ht_away=1,
        )
        is True
    )


def test_1h_under_1_5_won():
    assert (
        evaluate_inplay_tip(
            "1h_over_1_5",
            "no",
            home_score=1,
            away_score=1,
            ht_home=0,
            ht_away=1,
        )
        is True
    )


def test_home_plus_one_half_ft_won_on_draw():
    assert (
        evaluate_inplay_tip(
            "ft_hcap_home_p1_5",
            "yes",
            home_score=1,
            away_score=1,
        )
        is True
    )
