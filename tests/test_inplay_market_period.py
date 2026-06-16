"""Testes de guardrail por período de mercado."""

import pytest

from models.bet_guardrails import BetGuardrailError, validate_register_open_bet
from models.inplay_market_period import (
    allow_2h_suggestions,
    effective_guardrail_market,
    is_market_blocked_by_minute,
)


def test_ft_bloqueado_apos_45():
    assert is_market_blocked_by_minute("h2h", 46) is True
    assert is_market_blocked_by_minute("over_2_5", 46) is True


def test_2t_liberado_ate_82():
    assert is_market_blocked_by_minute("2h_over_0_5", 60) is False
    assert is_market_blocked_by_minute("2h_over_0_5", 83) is True
    assert allow_2h_suggestions(60) is True
    assert allow_2h_suggestions(45) is False


def test_registro_aposta_2t_no_segundo_tempo(monkeypatch):
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    monkeypatch.setattr("config.settings.live_block_2h_minute", 82)
    validate_register_open_bet(
        existing_bets=[],
        superbet_event_id=1,
        home_team="A",
        away_team="B",
        picks=[{"market": "2h_over_0_5", "outcome": "yes"}],
        minute=60,
    )


def test_registro_ft_bloqueado_no_2t(monkeypatch):
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.live_block_minute", 45)
    with pytest.raises(BetGuardrailError) as exc:
        validate_register_open_bet(
            existing_bets=[],
            superbet_event_id=1,
            home_team="A",
            away_team="B",
            picks=[{"market": "h2h", "outcome": "1"}],
            minute=60,
        )
    assert exc.value.code == "block_midgame"


def test_effective_guardrail_market_second_half_text():
    assert effective_guardrail_market("other", outcome="Vencedor 2º Tempo") == "2h_other"
    assert effective_guardrail_market("combo", outcome="1T over 1.5") == "1h_other"
