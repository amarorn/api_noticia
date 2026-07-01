"""Testes de sugestões Super Múltipla no advice."""

from __future__ import annotations

from models.super_multipla_suggestions import build_super_multipla_block


def _scan_row(market: str, outcome: str, odd: float, prob: float, label: str) -> dict:
    return {
        "market": market,
        "outcome": outcome,
        "market_odd": odd,
        "model_prob": prob,
        "expected_value": prob * odd - 1,
        "edge_pp": (prob - 1 / odd) * 100,
        "label": label,
        "meets_threshold": True,
    }


def test_build_super_multipla_block_returns_combos():
    scan = [
        _scan_row("h2h", "1", 1.80, 0.58, "Casa"),
        _scan_row("over_2_5", "yes", 2.10, 0.52, "Over 2.5"),
        _scan_row("btts", "yes", 1.90, 0.55, "Ambas marcam"),
    ]
    block = build_super_multipla_block(
        scan,
        superbet_event_id=13127506,
        minute=25,
        home_score=0,
        away_score=0,
    )
    assert block["bonus_pct"] == 0.05
    assert block["min_leg_odd_for_bonus"] == 1.35
    assert len(block["suggested_combos"]) >= 1
    combo = block["suggested_combos"][0]
    assert combo["combined_odd"] >= 3.0
    assert len(combo["legs"]) == 2
    assert combo["bonus_eligible"] is True
    assert combo["final_payout"] >= combo["potential_payout"]
