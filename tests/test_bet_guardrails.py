"""Testes das regras P0 de guardrails operacionais."""
from __future__ import annotations

import pytest

from models.bet_guardrails import (
    BetGuardrailError,
    build_bet_guardrails_payload,
    find_duplicate_open_bet,
    resolve_live_minute,
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


def test_blocks_other_market_after_45(monkeypatch):
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=123,
            home_team="Canadá",
            away_team="Bósnia e Herzegovina",
            picks=[{"market": "other", "outcome": "palpite genérico"}],
            minute=70,
        )
    assert exc.value.code == "block_midgame"


def test_hard_stop_at_88(monkeypatch):
    monkeypatch.setattr("config.settings.live_hard_stop_minute", 88)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=123,
            home_team="A",
            away_team="B",
            picks=[{"market": "2h_h2h", "outcome": "1"}],
            minute=90,
        )
    assert exc.value.code == "hard_stop"


def test_stake_cap(monkeypatch):
    monkeypatch.setattr("config.settings.bet_max_stake", 50.0)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=123,
            home_team="A",
            away_team="B",
            picks=[{"market": "h2h", "outcome": "1"}],
            minute=10,
            stake=75.0,
        )
    assert exc.value.code == "stake_cap"


def test_extension_requires_minute(monkeypatch):
    monkeypatch.setattr("config.settings.bet_require_minute_extension", True)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=None,
            home_team="A",
            away_team="B",
            picks=[{"market": "h2h", "outcome": "1"}],
            minute=None,
            source="superbet_extension",
        )
    assert exc.value.code == "minute_required"


def test_blocks_multis_late(monkeypatch):
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.bet_block_multis_late", True)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)

    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=123,
            home_team="A",
            away_team="B",
            picks=[
                {"market": "h2h", "outcome": "1"},
                {"market": "btts", "outcome": "yes"},
            ],
            minute=50,
        )
    assert exc.value.code == "block_multis_late"


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
    monkeypatch.setattr("config.settings.live_hard_stop_minute", 88)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.bet_max_stake", 50.0)

    payload = build_bet_guardrails_payload(
        minute=50,
        pregame_prediction="X",
        pregame_probs={"1": 0.3, "X": 0.35, "2": 0.35},
        inplay_probs={"1": 0.25, "X": 0.4, "2": 0.35},
    )
    assert payload["block_new_bets"] is True
    assert payload["block_minute"] == 45
    assert payload["hard_stop_minute"] == 88
    assert payload["max_stake"] == 50.0
    assert payload["pregame_palpite"] == "X"


def test_resolve_live_minute_from_local_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    monkeypatch.setattr(
        "models.bet_guardrails._minute_from_superbet_api",
        lambda **kwargs: None,
    )
    event_dir = tmp_path / "bronze" / "superbet" / "events" / "99999"
    event_dir.mkdir(parents=True)
    snap = {
        "event_id": 99999,
        "home_team": "Brasil",
        "away_team": "Egito",
        "is_live": True,
        "inplay": {"minute": 23, "home_score": 0, "away_score": 0},
    }
    (event_dir / "20260615T120000Z.json").write_text(
        __import__("json").dumps(snap),
        encoding="utf-8",
    )

    minute = resolve_live_minute(
        minute=None,
        superbet_event_id=99999,
        home_team="Brasil",
        away_team="Egito",
    )
    assert minute == 23
