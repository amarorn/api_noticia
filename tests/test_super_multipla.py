"""Testes de Super Múltipla — odds combinadas e bônus promo."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import settings
from models.super_multipla import (
    SuperMultiplaValidationError,
    calculate_multiple_odds,
    calculate_payout,
    calculate_super_multipla,
    round_money,
    validate_super_multipla_bonus,
)
from schemas.super_multipla import SuperMultiplaCalculateRequest, SuperMultiplaLegInput


def _leg(
    *,
    market: str = "h2h",
    outcome: str = "1",
    odd: float = 1.80,
    event_id: int = 13127506,
    model_prob: float | None = None,
) -> SuperMultiplaLegInput:
    return SuperMultiplaLegInput(
        market=market,
        outcome=outcome,
        market_odd=odd,
        superbet_event_id=event_id,
        is_live=True,
        model_prob=model_prob,
    )


def test_round_money_centavo():
    assert round_money(10.005) == 10.01
    assert round_money(10.004) == 10.0


def test_calculate_multiple_odds_product():
    legs = [{"market_odd": 1.80}, {"market_odd": 2.10}]
    assert calculate_multiple_odds(legs) == round_money(1.80 * 2.10)


def test_calculate_multiple_odds_min_legs():
    with pytest.raises(SuperMultiplaValidationError, match="2 pernas"):
        calculate_multiple_odds([{"market_odd": 2.0}])


def test_calculate_multiple_odds_min_odd():
    with pytest.raises(SuperMultiplaValidationError, match="1.01"):
        calculate_multiple_odds([{"market_odd": 1.0}, {"market_odd": 2.0}])


def test_super_multipla_bonus_eligible():
    legs = [{"market_odd": 1.80}, {"market_odd": 2.10}]
    eligible, pct = validate_super_multipla_bonus(legs)
    assert eligible is True
    assert pct == pytest.approx(0.05)


def test_super_multipla_bonus_not_eligible_low_odd():
    legs = [{"market_odd": 1.20}, {"market_odd": 2.10}]
    eligible, pct = validate_super_multipla_bonus(legs)
    assert eligible is False
    assert pct == 0.0


def test_calculate_payout_with_bonus():
    potential, final = calculate_payout(5.0, 3.78, 0.05)
    assert potential == round_money(5.0 * 3.78)
    assert final == round_money(potential * 1.05)


def test_calculate_super_multipla_full():
    req = SuperMultiplaCalculateRequest(
        legs=[
            _leg(odd=1.80, model_prob=0.58),
            _leg(market="over_2_5", outcome="yes", odd=2.10, model_prob=0.52),
        ],
        stake=5.0,
        bet_type="MULTIPLE",
        minute=23,
    )
    resp = calculate_super_multipla(req)
    assert resp.total_odds == round_money(1.80 * 2.10)
    assert resp.bonus_eligible is True
    assert resp.bonus_percentage == pytest.approx(0.05)
    assert resp.final_payout > resp.potential_payout
    assert resp.combined_prob == pytest.approx(0.58 * 0.52, rel=1e-4)
    assert resp.combined_ev is not None
    assert resp.builder_validation is not None
    assert "13127506" in resp.builder_validation


def test_calculate_super_multipla_stake_max(monkeypatch):
    monkeypatch.setattr(settings, "bet_max_stake", 10.0)
    req = SuperMultiplaCalculateRequest(
        legs=[_leg(odd=1.80), _leg(odd=2.10)],
        stake=15.0,
        bet_type="MULTIPLE",
    )
    with pytest.raises(SuperMultiplaValidationError, match="max_stake"):
        calculate_super_multipla(req)


def test_calculate_super_multipla_late_warning(monkeypatch):
    monkeypatch.setattr(settings, "bet_block_multis_late", True)
    monkeypatch.setattr(settings, "live_block_minute", 45)
    req = SuperMultiplaCalculateRequest(
        legs=[_leg(odd=1.80), _leg(odd=2.10)],
        stake=5.0,
        bet_type="MULTIPLE",
        minute=50,
    )
    resp = calculate_super_multipla(req)
    assert any("45" in w for w in resp.warnings)


def test_calculate_super_multipla_sgm_unders():
    """Under FT + Under 1T: odd SGM ~3.7, não produto 6.73."""
    req = SuperMultiplaCalculateRequest(
        legs=[
            _leg(market="over_3_5", outcome="no", odd=3.60, model_prob=0.325),
            _leg(market="1h_over_2_5", outcome="no", odd=1.87, model_prob=0.612),
        ],
        stake=5.0,
        bet_type="MULTIPLE",
        minute=26,
    )
    resp = calculate_super_multipla(req)
    assert resp.product_odds == pytest.approx(6.73, rel=1e-2)
    assert resp.pricing_mode == "bet_builder_sgm"
    assert resp.total_odds < 4.0
    assert resp.total_odds > 3.5
    assert resp.total_odds < resp.product_odds
    assert resp.combined_prob is not None
    assert resp.combined_prob > 0.325 * 0.612


def test_api_super_multipla_calculate(monkeypatch):
    from api.main import app

    monkeypatch.setattr(settings, "api_key", None)
    client = TestClient(app)
    resp = client.post(
        "/worldcup/superbet/multiple/calculate",
        json={
            "legs": [
                {
                    "market": "h2h",
                    "outcome": "1",
                    "market_odd": 1.80,
                    "superbet_event_id": 13127506,
                    "is_live": True,
                },
                {
                    "market": "over_2_5",
                    "outcome": "yes",
                    "market_odd": 2.10,
                    "superbet_event_id": 13127506,
                    "is_live": True,
                },
            ],
            "stake": 5.0,
            "bet_type": "MULTIPLE",
            "minute": 23,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["bonus_eligible"] is True
    assert data["total_odds"] == pytest.approx(3.78, rel=1e-3)
    assert data["final_payout"] > data["potential_payout"]
