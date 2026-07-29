"""Testes dos endpoints de beisebol."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app
from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState

client = TestClient(app)


def _snapshot() -> SuperbetEventSnapshot:
    return SuperbetEventSnapshot(
        event_id=12856152,
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        event_name="Hanwha Eagles·Kiwoom Heroes",
        utc_date="2026-07-16T09:30:00Z",
        betradar_id="67204684",
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=0,
            away_score=5,
            minute=5,
            stoppage_time=None,
            home_corners=0,
            away_corners=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="5I",
            status="STARTED",
            baseball_innings=[
                {"num": 1, "home": 0, "away": 1},
                {"num": 5, "home": 0, "away": 2},
            ],
        ),
        h2h_odds={},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        moneyline_odds={"1": 8.5, "2": 1.04},
        moneyline_implied={"1": 0.105, "2": 0.895},
        spread_odds={"p4_5": {"home": 1.78, "away": 1.92}},
        spread_implied={"p4_5": {"home": 0.53, "away": 0.47}},
        total_points_odds={},
        total_points_implied={},
        raw_market_count=9,
        captured_at="2026-07-16T10:00:00+00:00",
    )


class TestBaseballApi:
    def test_baseball_live_list(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        with patch("ingest.superbet.client.SuperbetClient.fetch_live_events") as mock_fetch:
            mock_fetch.return_value = []
            response = client.get("/baseball/superbet/live")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["sport_id"] == 20

    def test_baseball_advice(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        snap = _snapshot()
        with patch(
            "ingest.superbet.baseball_advice.fetch_event_with_stale_fallback",
            return_value=(snap, False),
        ), patch(
            "ingest.superbet.baseball_advice.save_event_snapshot",
        ):
            response = client.get("/baseball/superbet/live/12856152/advice?fast=true")
        assert response.status_code == 200
        data = response.json()
        assert data["home_team"] == "Hanwha Eagles"
        assert data["inning"] == 5
        assert data["inplay_summary"]["prob_away_win"] > data["inplay_summary"]["prob_home_win"]
        assert "aportes" in data

    def test_baseball_copilot(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        monkeypatch.setattr("config.settings.live_copilot_enabled", True)
        monkeypatch.setattr("config.settings.openai_api_key", "")
        advice = {
            "superbet_event_id": 12856152,
            "home_team": "Hanwha Eagles",
            "away_team": "Kiwoom Heroes",
            "inning": 5,
            "minute": 5,
            "current_score": "0x5",
            "period_label": "5I",
            "strategy": {"posture": "neutro", "wait_reason": "Aguardar", "shields": []},
            "aportes": [],
            "inplay_summary": {"expected_total": 9.1},
        }
        with patch(
            "ingest.superbet.live_advice_cache.get_stale_advice_for_event",
            return_value=advice,
        ):
            response = client.get("/baseball/superbet/live/12856152/copilot")
        assert response.status_code == 200
        data = response.json()
        assert data["sport"] == "baseball"
        assert data["event_id"] == 12856152
        assert data["acao_agora"] in {"apostar", "aguardar", "cashout"}
