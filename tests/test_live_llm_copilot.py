"""Testes do copiloto ao vivo (OpenAI mockado)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from models.live_llm_copilot import run_live_copilot


@pytest.fixture
def football_advice() -> dict:
    return {
        "superbet_event_id": 123,
        "home_team": "Brasil",
        "away_team": "Egito",
        "minute": 67,
        "current_score": "2x1",
        "period_label": "2T",
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


def test_copilot_disabled_without_api_key(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", None)
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_enabled", True)

    result = run_live_copilot(football_advice, sport="football")

    assert result["enabled"] is False
    assert result["picks"]
    assert result["acao_agora"] == "apostar"


def test_copilot_validates_picks_against_whitelist(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_enabled", True)

    llm_json = {
        "momento": "Mercado ainda subestima gols.",
        "acao_agora": "apostar",
        "confianca_geral": "Alta",
        "picks": [
            {
                "rank": 1,
                "market": "over_2_5",
                "outcome": "yes",
                "label": "Over 2.5",
                "rationale": "Edge forte no total.",
                "confidence": "Alta",
            },
            {
                "rank": 2,
                "market": "h2h",
                "outcome": "1",
                "label": "Brasil vence",
                "rationale": "Inventado",
                "confidence": "Alta",
            },
        ],
        "alertas": ["Evite combo correlacionado."],
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "model": "gpt-4o-mini",
        "choices": [{"message": {"content": json.dumps(llm_json)}}],
        "usage": {"total_tokens": 100},
    }

    with patch("models.live_llm_copilot.httpx.post", return_value=mock_response):
        result = run_live_copilot(football_advice, sport="football")

    assert result["available"] is True
    assert len(result["picks"]) == 1
    assert result["picks"][0]["market"] == "over_2_5"
    assert result["model"] == "gpt-4o-mini"


def test_copilot_openai_http_error_falls_back(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_enabled", True)
    monkeypatch.setattr("models.live_llm_copilot.get_cached_copilot", lambda _key: None)
    monkeypatch.setattr("models.live_llm_copilot.set_cached_copilot", lambda *_a, **_k: None)

    response = MagicMock()
    response.status_code = 429
    response.text = "rate limit"
    error = httpx.HTTPStatusError("429", request=MagicMock(), response=response)

    with patch("models.live_llm_copilot.httpx.post", side_effect=error):
        result = run_live_copilot(football_advice, sport="football")

    assert "429" in (result.get("error") or "")
    assert result["picks"]


def test_copilot_basket_from_aportes(monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", None)
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_enabled", True)

    advice = {
        "superbet_event_id": 999,
        "home_team": "Lakers",
        "away_team": "Celtics",
        "minute": 36,
        "current_score": "88x82",
        "aportes": [
            {
                "market": "total_points",
                "outcome": "over",
                "label": "Over 224.5",
                "action": "apostar",
                "model_prob": 0.58,
                "market_odd": 1.9,
                "expected_value": 0.1,
                "edge_pp": 5.5,
                "suggested_stake_pct": 0.8,
            }
        ],
    }

    result = run_live_copilot(advice, sport="basketball")
    assert result["sport"] == "basketball"
    assert result["picks"][0]["label"] == "Over 224.5"


def test_baseball_fallback_without_openai(monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_enabled", True)
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", "")

    advice = {
        "superbet_event_id": 501,
        "home_team": "Yankees",
        "away_team": "Red Sox",
        "inning": 6,
        "minute": 6,
        "current_score": "4x2",
        "period_label": "6I",
        "strategy": {"posture": "atacar", "wait_reason": None, "shields": []},
        "game_phase": {"phase": "mid", "label": "meio do jogo"},
        "inplay_summary": {"expected_total": 8.4, "market_total_line": 8.5},
        "aportes": [
            {
                "market": "moneyline",
                "outcome": "1",
                "label": "Yankees",
                "action": "apostar",
                "model_prob": 0.71,
                "market_odd": 1.65,
                "expected_value": 0.17,
                "edge_pp": 8.2,
                "suggested_stake_pct": 1.1,
            }
        ],
    }

    result = run_live_copilot(advice, sport="baseball")
    assert result["sport"] == "baseball"
    assert result["acao_agora"] == "apostar"
    assert result["picks"][0]["label"] == "Yankees"
    assert "6I" in result["momento"]


def test_baseball_candidates_merge_strategy_and_aportes():
    from models.live_llm_copilot import _baseball_candidates

    advice = {
        "strategy": {
            "opportunities": [
                {
                    "market": "total_runs",
                    "outcome": "over_8_5",
                    "label": "Over 8.5",
                    "expected_value": 0.12,
                    "edge_pp": 6.0,
                }
            ],
            "watch_list": [],
        },
        "aportes": [
            {
                "market": "moneyline",
                "outcome": "1",
                "label": "Casa",
                "action": "apostar",
                "expected_value": 0.08,
            }
        ],
    }
    rows = _baseball_candidates(advice)
    markets = {r["market"] for r in rows}
    assert "total_runs" in markets
    assert "moneyline" in markets


def test_get_stale_copilot_for_event():
    from models.live_copilot_cache import get_stale_copilot_for_event, set_cached_copilot

    payload = {"event_id": 7, "momento": "teste", "acao_agora": "aguardar"}
    key = ("football", 7, "1x0", 10, "neutro", "h2h", "1", 0.1)
    set_cached_copilot(key, payload, ttl_sec=30.0)

    stale = get_stale_copilot_for_event(7)
    assert stale is not None
    assert stale["momento"] == "teste"

    missing = get_stale_copilot_for_event(999)
    assert missing is None


def test_warm_live_copilot_skips_when_disabled(football_advice, monkeypatch):
    monkeypatch.setattr("models.live_llm_copilot.settings.live_copilot_poll_enabled", False)
    monkeypatch.setattr("models.live_llm_copilot.settings.openai_api_key", "sk-test")

    from models.live_llm_copilot import warm_live_copilot

    assert warm_live_copilot(football_advice, sport="football") is None
