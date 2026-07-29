"""Testes de rótulos Superbet para basquete."""
from __future__ import annotations

from models.basket_market_labels import format_basket_selection_label, resolve_basket_market_display


def test_resolve_quarter_spread_market_name():
    display = resolve_basket_market_display(
        "quarter_2_spread",
        quarter=2,
        market_names={"q2_spread": "2º Quarto - Handicap"},
    )
    assert display == "2º Quarto - Handicap"


def test_format_odd_even_selection():
    assert format_basket_selection_label("odd_even", outcome="even") == "Par"
    display = resolve_basket_market_display(
        "odd_even",
        market_names={"odd_even": "Ímpar/Par (Inc. prorrogação)"},
    )
    assert display == "Ímpar/Par (Inc. prorrogação)"


def test_format_quarter_spread_selection():
    label = format_basket_selection_label(
        "quarter_2_spread",
        team="Dallas Wings (F)",
        line=8.5,
    )
    assert label == "Dallas Wings (F) +8.5"
