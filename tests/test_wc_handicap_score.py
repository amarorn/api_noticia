"""Handicap vs placar ao vivo."""
from __future__ import annotations

from models.wc_handicap_score import (
    assess_handicap_vs_live_score,
    format_handicap_label_with_score,
    handicap_blocked_by_score,
    mirror_line_key,
    paired_handicap_line_keys,
    superbet_handicap_help,
    superbet_handicap_line_label,
)


def test_away_minus_half_losing_needs_win():
    """Hawassa −0.5 com placar 1×0 contra visitante exige vitória."""
    assessment = assess_handicap_vs_live_score(
        "ft_hcap_away_m0_5",
        home_score=1,
        away_score=0,
        minute=55,
        home_team="Negele Arsi Ketema",
        away_team="Hawassa Kenema",
    )
    assert assessment is not None
    assert assessment.status == "needs_win"
    assert assessment.block_suggestion is False
    assert "precisa vencer" in assessment.score_hint.lower()


def test_handicap_button_on_book():
    from models.wc_handicap_score import handicap_button_on_book

    half_markets = {
        "ft": {
            "handicap": {
                "m1_5": {"home": 1.97},
                "p1_5": {"away": 1.80},
            },
        },
    }
    assert handicap_button_on_book(half_markets, period="ft", side="away", line_key="p1_5")
    assert not handicap_button_on_book(half_markets, period="ft", side="home", line_key="p1_5")
    assert mirror_line_key("m0_5") == "p0_5"
    assert paired_handicap_line_keys("m0_5") == ("m0_5", "p0_5")
    assert superbet_handicap_line_label("home", "m0_5") == "-0.5"
    assert superbet_handicap_line_label("away", "m0_5") == "-0.5"
    from models.wc_handicap_score import model_prob_key_for_book_handicap

    assert model_prob_key_for_book_handicap("away", "m0_5") == "away_p0_5"
    assert model_prob_key_for_book_handicap("home", "p1_5") == "home_p1_5"
    help_text = superbet_handicap_help("Negele", "Hawassa", "away", "m0_5")
    assert "-0.5" in help_text
    assert "vencer" in help_text.lower()


def test_away_minus_half_losing_blocks_unrealistic_comeback():
    assessment = assess_handicap_vs_live_score(
        "ft_hcap_away_m0_5",
        home_score=4,
        away_score=0,
        minute=70,
        away_team="Hawassa Kenema",
    )
    assert assessment is not None
    assert assessment.block_suggestion is True
    assert assessment.status == "needs_comeback"


def test_home_minus_half_leading_on_track():
    assessment = assess_handicap_vs_live_score(
        "ft_hcap_home_m0_5",
        home_score=1,
        away_score=0,
        minute=30,
        home_team="Casa",
    )
    assert assessment is not None
    assert assessment.status == "on_track"
    assert assessment.block_suggestion is False


def test_1h_handicap_blocked_after_halftime_lost():
    blocked, reason = handicap_blocked_by_score(
        "1h_hcap_away_m0_5",
        home_score=1,
        away_score=0,
        minute=50,
        ht_home=1,
        ht_away=0,
    )
    assert blocked is True
    assert "encerado" in reason.lower() or "perdeu" in reason.lower()


def test_format_handicap_label_includes_score_hint():
    assessment = assess_handicap_vs_live_score(
        "ft_hcap_away_m0_5",
        home_score=1,
        away_score=0,
        minute=55,
        away_team="Hawassa Kenema",
    )
    label = format_handicap_label_with_score(
        "Jogo — Hawassa Kenema handicap -0.5",
        assessment,
    )
    assert "precisa vencer" in label.lower()
