"""Testes dos endpoints de basquete."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def _basket_snapshot_dict() -> dict:
    return {
        "event_id": 123,
        "home_team": "LAL",
        "away_team": "GSW",
        "event_name": "LAL·GSW",
        "utc_date": None,
        "betradar_id": None,
        "is_live": True,
        "inplay": {
            "home_score": 50,
            "away_score": 45,
            "minute": 24,
            "stoppage_time": None,
            "home_corners": 0,
            "away_corners": 0,
            "home_yellow_cards": 0,
            "away_yellow_cards": 0,
            "ht_home_score": None,
            "ht_away_score": None,
            "period_label": "2º Quarto",
            "status": "LIVE",
        },
        "h2h_odds": {},
        "h2h_implied": {},
        "totals": {},
        "totals_implied": {},
        "corners": {},
        "corners_implied": {},
        "combo_markets": {},
        "btts_odds": {},
        "next_goal_odds": {},
        "generosity_probs": {},
        "team_totals": {"home": {}, "away": {}},
        "first_half_totals": {},
        "second_half_totals": {},
        "yellow_cards": {},
        "first_half_yellow_cards": {},
        "team_shots": {"home": {}, "away": {}},
        "team_shots_on_target": {"home": {}, "away": {}},
        "half_markets": {},
        "handicap_odds": {},
        "handicap_implied": {},
        "moneyline_odds": {"1": 1.75, "2": 2.10},
        "moneyline_implied": {"1": 0.5455, "2": 0.4545},
        "spread_odds": {"m5_5": {"home": 1.90, "away": 1.90}},
        "spread_implied": {"m5_5": {"home": 0.5, "away": 0.5}},
        "total_points_odds": {"220.5": {"over": 1.90, "under": 1.90}},
        "total_points_implied": {"220.5": {"over": 0.5, "under": 0.5}},
        "raw_market_count": 3,
        "captured_at": "2026-01-01T00:00:00+00:00",
    }


class TestBasketApi:
    def test_basket_live_list(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        with patch("ingest.superbet.client.SuperbetClient.fetch_live_events") as mock_fetch:
            mock_fetch.return_value = []
            response = client.get("/basket/superbet/live")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["sport_id"] is not None

    def test_basket_event_snapshot(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        with patch(
            "api.routers.basket.fetch_event_with_stale_fallback"
        ) as mock_fetch:
            from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState

            snapshot = SuperbetEventSnapshot(
                event_id=123,
                home_team="LAL",
                away_team="GSW",
                event_name="LAL·GSW",
                utc_date=None,
                betradar_id=None,
                is_live=True,
                inplay=SuperbetInPlayState(
                    home_score=50,
                    away_score=45,
                    minute=24,
                    stoppage_time=None,
                    home_corners=0,
                    away_corners=0,
                    home_yellow_cards=0,
                    away_yellow_cards=0,
                    ht_home_score=None,
                    ht_away_score=None,
                    period_label="2º Quarto",
                    status="LIVE",
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
                moneyline_odds={"1": 1.75, "2": 2.10},
                moneyline_implied={},
                spread_odds={"m5_5": {"home": 1.90, "away": 1.90}},
                spread_implied={},
                total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
                total_points_implied={},
            )
            mock_fetch.return_value = (snapshot, False)
            response = client.get("/basket/superbet/events/123")
        assert response.status_code == 200
        data = response.json()
        assert data["home_team"] == "LAL"
        assert data["away_team"] == "GSW"
        assert data["moneyline_odds"]["1"] == pytest.approx(1.75)

    def test_basket_live_advice(self, monkeypatch):
        monkeypatch.setattr("config.settings.api_key", None)
        with patch(
            "api.routers.basket.run_basket_live_advice"
        ) as mock_advice:
            mock_advice.return_value = {
                "home_team": "LAL",
                "away_team": "GSW",
                "minute": 24,
                "current_score": "50x45",
                "period_label": "2º Quarto",
                "status": "LIVE",
                "is_finished": False,
                "is_live": True,
                "superbet_stale": False,
                "superbet_event_id": 123,
                "sport_id": 7,
                "captured_at": "2026-01-01T00:00:00+00:00",
                "h2h_odds": {"1": 1.75, "2": 2.10},
                "h2h_implied": {"1": 0.5455, "2": 0.4545},
                "spread_odds": {"m5_5": {"home": 1.90, "away": 1.90}},
                "spread_implied": {},
                "total_points_odds": {"220.5": {"over": 1.90, "under": 1.90}},
                "total_points_implied": {},
                "inplay_summary": {
                    "prob_home_win": 0.55,
                    "prob_away_win": 0.45,
                    "expected_final_home": 110.0,
                    "expected_final_away": 105.0,
                    "expected_total": 215.0,
                    "remaining_minutes": 24.0,
                    "moneyline_probs": {"1": 0.55, "2": 0.45},
                    "spread_probs": {},
                    "total_probs": {},
                    "ppm_home": 2.3,
                    "ppm_away": 2.1,
                },
                "aportes": [],
                "confidence": {"score": 0.6, "label": "Média", "max_edge_pp": 0.0},
            }
            response = client.get("/basket/superbet/live/123/advice")
        assert response.status_code == 200
        data = response.json()
        assert data["home_team"] == "LAL"
        assert data["inplay_summary"]["prob_home_win"] == pytest.approx(0.55)
