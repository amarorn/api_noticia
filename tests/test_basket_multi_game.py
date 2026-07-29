"""Testes de bilhetes multi-jogo de basquete."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from models.basket_multi_game_tickets import build_basket_multi_game_tickets, pick_best_leg_from_advice

client = TestClient(app)


def _advice(
    event_id: int,
    home: str,
    away: str,
    *,
    ev: float = 0.08,
    odd: float = 1.85,
    action: str = "apostar",
) -> dict:
    return {
        "superbet_event_id": event_id,
        "home_team": home,
        "away_team": away,
        "minute": 24,
        "current_score": "50-45",
        "is_live": True,
        "aportes": [
            {
                "market": "moneyline",
                "outcome": "1",
                "label": f"{home} vence",
                "model_prob": 0.58,
                "market_odd": odd,
                "implied_prob": 1 / odd,
                "expected_value": ev,
                "edge_pp": 8.0,
                "kelly_quarter": 0.02,
                "suggested_stake_pct": 0.02,
                "action": action,
            },
            {
                "market": "total",
                "outcome": "over_220_5",
                "label": "Over 220.5",
                "model_prob": 0.52,
                "market_odd": 1.90,
                "implied_prob": 0.526,
                "expected_value": 0.02,
                "edge_pp": 2.0,
                "kelly_quarter": 0.005,
                "suggested_stake_pct": 0.005,
                "action": "monitorar",
            },
        ],
    }


class TestPickBestLeg:
    def test_prefers_apostar_over_monitorar(self):
        advice = _advice(1, "LAL", "GSW")
        leg = pick_best_leg_from_advice(advice)
        assert leg is not None
        assert leg["action"] == "apostar"
        assert leg["market"] == "moneyline"

    def test_returns_none_without_aportes(self):
        assert pick_best_leg_from_advice({"aportes": []}) is None


class TestBuildBasketMultiGameTickets:
    def test_builds_ticket_with_two_games(self):
        payload = build_basket_multi_game_tickets(
            {
                101: _advice(101, "LAL", "GSW", ev=0.10, odd=1.90),
                102: _advice(102, "BOS", "MIA", ev=0.07, odd=1.80),
            },
            bankroll=1000,
            stake=10,
            max_tickets=3,
        )
        assert payload["games_with_pick"] == 2
        assert len(payload["suggested_tickets"]) >= 1
        ticket = payload["suggested_tickets"][0]
        assert len(ticket["legs"]) == 2
        assert ticket["combined_odd"] > 1.0
        assert ticket["combined_ev"] is not None

    def test_skips_game_without_aportes(self):
        payload = build_basket_multi_game_tickets(
            {
                101: _advice(101, "LAL", "GSW"),
                102: {"superbet_event_id": 102, "home_team": "BOS", "away_team": "MIA", "aportes": []},
            },
        )
        assert payload["games_with_pick"] == 1
        assert len(payload["skipped_events"]) == 1
        assert payload["skipped_events"][0]["reason"] == "sem_aportes"


class TestBasketMultiGameApi:
    def test_endpoint_returns_tickets(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)

        def fake_advice(event_id: int, **kwargs):
            teams = {201: ("LAL", "GSW"), 202: ("BOS", "MIA")}
            home, away = teams[event_id]
            return _advice(event_id, home, away)

        with patch("api.routers.basket.run_basket_live_advice", side_effect=fake_advice):
            response = client.post(
                "/basket/superbet/multi-game/tickets",
                json={"event_ids": [201, 202], "bankroll": 1000, "stake": 10, "fast": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["games_evaluated"] == 2
        assert data["games_with_pick"] == 2
        assert len(data["suggested_tickets"]) >= 1

    def test_endpoint_requires_two_events(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        response = client.post(
            "/basket/superbet/multi-game/tickets",
            json={"event_ids": [201]},
        )
        assert response.status_code == 422
