"""Testes da camada de decisão de apostas."""
from __future__ import annotations

from models.bet_decision import assess_bet_recommendation, is_blocked_market
from models.bet_observability import get_bet_observability_metrics, reset_bet_observability_metrics


def setup_function() -> None:
    reset_bet_observability_metrics()


def test_blocks_unknown_market() -> None:
    decision = assess_bet_recommendation(
        market="unknown",
        outcome="1",
        ev=0.12,
        edge_pp=10.0,
        model_prob=0.5,
        odd=2.2,
    )
    assert decision.allowed is False
    assert decision.classification == "avoid"
    metrics = get_bet_observability_metrics()
    assert metrics["blocked_unknown_market"] >= 1


def test_blocks_ev_below_threshold() -> None:
    decision = assess_bet_recommendation(
        market="h2h",
        outcome="1",
        ev=0.03,
        edge_pp=8.0,
        model_prob=0.45,
        odd=2.1,
        min_ev_threshold=0.05,
    )
    assert decision.allowed is False
    metrics = get_bet_observability_metrics()
    assert metrics["blocked_below_threshold"] >= 1


def test_allows_value_bet_above_threshold() -> None:
    decision = assess_bet_recommendation(
        market="h2h",
        outcome="1",
        ev=0.12,
        edge_pp=10.0,
        model_prob=0.48,
        odd=2.4,
        min_ev_threshold=0.05,
    )
    assert decision.allowed is True
    assert decision.classification in {"watch", "value_bet", "high_confidence"}
    assert decision.suggested_stake_brl > 0
    metrics = get_bet_observability_metrics()
    assert metrics["recommendations_allowed"] >= 1


def test_is_blocked_market_other() -> None:
    assert is_blocked_market("other") is True
    assert is_blocked_market("h2h") is False
