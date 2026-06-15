"""Testes de inferência de mercados legados ``other``."""
from __future__ import annotations

from models.bet_market_infer import infer_other_market


def test_infer_corners_under_from_legacy_outcome():
    inferred = infer_other_market("Menos de 15.5")
    assert inferred is not None
    market, outcome, line = inferred
    assert market == "corners_total"
    assert outcome == "under"
    assert line == "15.5"


def test_infer_corners_over():
    inferred = infer_other_market("Mais de 16.5")
    assert inferred == ("corners_total", "over", "16.5")


def test_infer_odd_even_goals():
    inferred = infer_other_market("Ímpar")
    assert inferred == ("odd_even_goals", "odd", None)
