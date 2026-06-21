"""Testes de odd combinada Criar Aposta (SGM vs produto simples)."""

from __future__ import annotations

from models.bet_builder_odds import product_odds, resolve_combined_odds


def test_under_ft_and_1h_uses_sgm_not_product():
    """Caso real: under 3.5 FT @3.60 + under 2.5 1T @1.87 → ~3.75 SGM, não 6.73."""
    legs = [
        {
            "market": "over_3_5",
            "outcome": "no",
            "market_odd": 3.60,
            "model_prob": 0.325,
            "superbet_event_id": 999,
        },
        {
            "market": "1h_over_2_5",
            "outcome": "no",
            "market_odd": 1.87,
            "model_prob": 0.612,
            "superbet_event_id": 999,
        },
    ]
    simple = product_odds(legs)
    assert simple == 6.73

    final, product, mode = resolve_combined_odds(legs)
    assert product == 6.73
    assert mode == "bet_builder_sgm"
    assert final < 4.0
    assert final > 3.5
    assert final < simple


def test_cross_event_keeps_product():
    legs = [
        {"market": "h2h", "outcome": "1", "market_odd": 2.0, "superbet_event_id": 1},
        {"market": "h2h", "outcome": "1", "market_odd": 2.5, "superbet_event_id": 2},
    ]
    final, product, mode = resolve_combined_odds(legs)
    assert mode == "product"
    assert final == 5.0
    assert product == 5.0
