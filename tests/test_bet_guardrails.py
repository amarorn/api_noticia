"""Testes das regras P0 de guardrails operacionais."""
from __future__ import annotations

import pytest

from models.bet_guardrails import (
    BetGuardrailError,
    build_bet_guardrails_payload,
    find_duplicate_open_bet,
    validate_register_open_bet,
)


def test_block_new_bets_after_45(monkeypatch):
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=123,
            home_team="Canadá",
            away_team="Bósnia e Herzegovina",
            picks=[{"market": "h2h", "outcome": "2"}],
            minute=46,
        )
    assert exc.value.code == "block_midgame"


def test_allows_bet_before_45(monkeypatch):
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.bet_one_per_market_enabled", True)

    validate_register_open_bet(
        existing_bets=[],
        superbet_event_id=123,
        home_team="Canadá",
        away_team="Bósnia e Herzegovina",
        picks=[{"market": "h2h", "outcome": "X"}],
        minute=30,
    )


def test_rejects_duplicate_market(monkeypatch):
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.bet_one_per_market_enabled", True)

    existing = [
        {
            "id": "bet-1",
            "status": "open",
            "superbet_event_id": 12512390,
            "home_team": "Canadá",
            "away_team": "Bósnia e Herzegovina",
            "picks": [{"market": "h2h", "outcome": "2"}],
        }
    ]

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=existing,
            superbet_event_id=12512390,
            home_team="Canadá",
            away_team="Bósnia e Herzegovina",
            picks=[{"market": "h2h", "outcome": "Bósnia"}],
            minute=20,
        )
    assert exc.value.code == "duplicate_market"


def test_find_duplicate_normalizes_h2h_outcome():
    existing = [
        {
            "id": "bet-1",
            "status": "open",
            "superbet_event_id": 1,
            "home_team": "A",
            "away_team": "B",
            "picks": [{"market": "h2h", "outcome": "2"}],
        }
    ]
    dup = find_duplicate_open_bet(
        existing,
        superbet_event_id=1,
        home_team="A",
        away_team="B",
        picks=[{"market": "h2h", "outcome": "away"}],
    )
    assert dup is not None
    assert dup["id"] == "bet-1"


def test_build_guardrails_payload_blocks_at_45(monkeypatch):
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    payload = build_bet_guardrails_payload(
        minute=50,
        pregame_prediction="X",
        pregame_probs={"1": 0.3, "X": 0.35, "2": 0.35},
        inplay_probs={"1": 0.25, "X": 0.4, "2": 0.35},
    )
    assert payload["block_new_bets"] is True
    assert payload["block_minute"] == 45
    assert payload["pregame_palpite"] == "X"
