"""Testes de propostas de combo enviadas pelo frontend à estação."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def _valid_proposal_payload(**overrides):
    payload = {
        "event_name": "Brasil × Marrocos",
        "home_team": "Brasil",
        "away_team": "Marrocos",
        "picks": [
            {
                "market": "h2h",
                "outcome": "X",
                "target_value": "Empate",
                "model_prob": 0.72,
                "market_odd": 1.35,
                "expected_value": 0.08,
                "edge_pp": 12.0,
            },
            {
                "market": "over_2_5",
                "outcome": "no",
                "target_value": "Menos 2.5",
                "model_prob": 0.65,
                "market_odd": 1.45,
                "expected_value": 0.05,
                "edge_pp": 8.0,
            },
        ],
        "stake": 20.0,
        "odds_placed": 1.95,
        "potential_return": 39.0,
        "source": "bolao_proposal",
        "minute": 80,
        "model_source": "inplay_market_scan",
        "combined_ev": 0.12,
        "combined_prob": 0.468,
    }
    payload.update(overrides)
    return payload


def test_register_combo_proposal_skips_midgame_guardrail(monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.api_key", "")
    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    monkeypatch.setattr("config.settings.bet_guardrails_enabled", True)
    monkeypatch.setattr("config.settings.live_block_minute", 45)

    client = TestClient(app)
    res = client.post("/user/open-bets", json=_valid_proposal_payload())
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "proposal"
    assert "estação" in body["message"].lower() or "Proposta" in body["message"]

    listed = client.get("/user/open-bets").json()
    assert listed["count"] >= 1
    assert any(b.get("status") == "proposal" for b in listed["bets"])


def test_register_combo_proposal_rejects_without_market_model(monkeypatch, tmp_path):
    monkeypatch.setattr("config.settings.api_key", "")
    monkeypatch.setattr("config.settings.lake_root", tmp_path)

    client = TestClient(app)
    payload = _valid_proposal_payload()
    payload["picks"][0].pop("market_odd")
    payload["combined_ev"] = -0.1

    res = client.post("/user/open-bets", json=payload)
    assert res.status_code == 422
    assert "mercado" in res.json()["detail"].lower() or "odd" in res.json()["detail"].lower()
