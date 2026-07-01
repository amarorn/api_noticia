"""Gate handicap −0,5 2T quando favorita só perde por 1."""
from __future__ import annotations

from models.wc_bet_advice import is_premature_underdog_handicap_2h


def test_blocks_away_minus_half_when_home_favorite_trailing():
    blocked, reason = is_premature_underdog_handicap_2h(
        "2h_hcap_away_m0_5",
        {
            "current_score": "0x1",
            "pregame_probs": {"1": 0.60, "X": 0.23, "2": 0.17},
        },
        minute=50,
    )
    assert blocked is True
    assert "Favorita" in reason


def test_allows_when_gap_two():
    blocked, _ = is_premature_underdog_handicap_2h(
        "2h_hcap_away_m0_5",
        {
            "current_score": "0x2",
            "pregame_probs": {"1": 0.60, "X": 0.23, "2": 0.17},
        },
        minute=50,
    )
    assert blocked is False
