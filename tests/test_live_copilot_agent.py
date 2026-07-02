"""Testes do copiloto agente ao vivo (OpenAI mockado)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from models.live_copilot_agent import run_live_copilot_agent


@pytest.fixture
def football_advice() -> dict:
    return {
        "superbet_event_id": 123,
        "home_team": "Brasil",
        "away_team": "Egito",
        "minute": 67,
        "current_score": "2x1",
        "period_label": "2T",
        "is_live": True,
        "is_finished": False,
        "confidence": {"score": 0.72, "label": "Alta"},
        "strategy": {
            "posture": "atacar",
            "wait_reason": "",
            "cashout": None,
            "opportunities": [
                {
                    "rank": 1,
                    "market": "over_2_5",
                    "outcome": "yes",
                    "label": "Over 2.5",
                    "tier": "forte",
                    "model_prob": 0.71,
                    "market_odd": 1.85,
                    "expected_value": 0.31,
                    "edge_pp": 12.4,
                    "suggested_stake_pct": 1.2,
                }
            ],
            "watch_list": [],
            "shields": [],
        },
    }


def test_agent_disabled_in_narrate_mode(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_copilot_agent.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_enabled", True)
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_mode", "narrate")

    result = run_live_copilot_agent(football_advice, sport="football", message="O que apostar?")

    assert result["mode"] == "narrate"
    assert result["enabled"] is False
    assert result["reply"]
    assert result["picks"]


def test_agent_runs_tools_and_returns_reply(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_copilot_agent.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_enabled", True)
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_mode", "agent")
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_max_agent_turns", 4)

    final_json = {
        "reply": "Over 2.5 ainda tem edge com o jogo aberto.",
        "momento": "67' — mercado subestima gols.",
        "acao_agora": "apostar",
        "confianca_geral": "Alta",
        "picks": [
            {
                "rank": 1,
                "market": "over_2_5",
                "outcome": "yes",
                "label": "Over 2.5",
                "rationale": "EV positivo.",
                "confidence": "Alta",
            }
        ],
        "alertas": [],
        "ui_actions": [
            {"type": "switch_tab", "tab": "mercados"},
        ],
    }

    tool_call_msg = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_opportunities", "arguments": "{}"},
            }
        ],
    }
    final_msg = {"role": "assistant", "content": json.dumps(final_json)}

    responses = [
        {"model": "gpt-4o-mini", "choices": [{"finish_reason": "tool_calls", "message": tool_call_msg}]},
        {"model": "gpt-4o-mini", "choices": [{"finish_reason": "stop", "message": final_msg}]},
    ]

    def fake_post(*_args, **_kwargs):
        data = responses.pop(0)
        mock = MagicMock()
        mock.raise_for_status = MagicMock()
        mock.json.return_value = data
        return mock

    with patch("models.live_copilot_agent.httpx.post", side_effect=fake_post):
        result = run_live_copilot_agent(
            football_advice,
            sport="football",
            message="Vale over 2.5 agora?",
        )

    assert result["available"] is True
    assert "get_opportunities" in result["tools_used"]
    assert result["reply"].startswith("Over 2.5")
    assert len(result["picks"]) == 1
    assert result["ui_actions"][0]["type"] == "switch_tab"


def test_agent_validates_ticket_legs(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_copilot_agent.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_enabled", True)
    monkeypatch.setattr("models.live_copilot_agent.settings.live_copilot_mode", "agent")

    final_json = {
        "reply": "Plano montado.",
        "momento": "67'",
        "acao_agora": "apostar",
        "confianca_geral": "Alta",
        "picks": [],
        "alertas": [],
        "ui_actions": [
            {
                "type": "add_ticket_legs",
                "legs": [
                    {"market": "over_2_5", "outcome": "yes", "label": "Over 2.5"},
                    {"market": "h2h", "outcome": "1", "label": "Inventado"},
                ],
            }
        ],
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "model": "gpt-4o-mini",
        "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(final_json)}}],
    }

    with patch("models.live_copilot_agent.httpx.post", return_value=mock_response):
        result = run_live_copilot_agent(football_advice, sport="football", message="Monta bilhete")

    add_actions = [a for a in result["ui_actions"] if a["type"] == "add_ticket_legs"]
    assert len(add_actions) == 1
    assert len(add_actions[0]["legs"]) == 1
    assert add_actions[0]["legs"][0]["market"] == "over_2_5"
