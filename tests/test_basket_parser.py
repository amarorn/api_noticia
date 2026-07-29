"""Testes de extração de mercados de basquete no parser Superbet."""
from __future__ import annotations

import pytest

from ingest.superbet.parser import parse_superbet_event


def _basket_event_payload(
    *,
    moneyline: dict[str, float] | None = None,
    spread: dict[str, dict[str, float]] | None = None,
    total: dict[str, dict[str, float]] | None = None,
) -> dict:
    markets = []
    if moneyline:
        markets.append({
            "name": "Vencedor da Partida",
            "odds": [
                {"price": moneyline["1"], "status": 1, "metadata": {"code": "1", "name": "1"}},
                {"price": moneyline["2"], "status": 1, "metadata": {"code": "2", "name": "2"}},
            ],
        })
    if spread:
        for line_key, sides in spread.items():
            odds = []
            for side, price in sides.items():
                code = "1" if side == "home" else "2"
                odds.append({
                    "price": price,
                    "status": 1,
                    "metadata": {
                        "code": code,
                        "name": side,
                        "special_bet_value": line_key.replace("_", ".").replace("m", "-").replace("p", "+"),
                    },
                })
            markets.append({"name": "Handicap", "odds": odds})
    if total:
        for line, sides in total.items():
            odds = []
            for outcome, price in sides.items():
                name = "over" if outcome == "over" else "under"
                odds.append({
                    "price": price,
                    "status": 1,
                    "metadata": {
                        "name": name,
                        "special_bet_value": line,
                    },
                })
            markets.append({"name": "Total de Pontos", "odds": odds})

    return {
        "event_id": 123,
        "fixture": {
            "event_name": "Los Angeles Lakers·Golden State Warriors",
            "sport_id": 7,
            "event_tags": "superLive",
        },
        "inplay_stats": {
            "home_team_score": 50,
            "away_team_score": 45,
            "minutes": 6,
            "periods": [
                {"num": 1, "home_team_score": 28, "away_team_score": 25},
                {"num": 2, "home_team_score": 22, "away_team_score": 20},
                {"num": 3, "home_team_score": 0, "away_team_score": 0},
            ],
        },
        "markets": markets,
    }


class TestBasketParser:
    def test_extract_moneyline(self):
        payload = _basket_event_payload(moneyline={"1": 1.75, "2": 2.10})
        snapshot = parse_superbet_event(payload)
        assert snapshot.moneyline_odds == {"1": 1.75, "2": 2.10}
        assert "1" in snapshot.moneyline_implied
        assert "2" in snapshot.moneyline_implied

    def test_extract_spread(self):
        payload = _basket_event_payload(spread={"m5_5": {"home": 1.90, "away": 1.90}})
        snapshot = parse_superbet_event(payload)
        assert "m5_5" in snapshot.spread_odds
        assert snapshot.spread_odds["m5_5"]["home"] == pytest.approx(1.90)
        assert snapshot.spread_odds["m5_5"]["away"] == pytest.approx(1.90)

    def test_extract_total_points(self):
        payload = _basket_event_payload(total={"220.5": {"over": 1.90, "under": 1.90}})
        snapshot = parse_superbet_event(payload)
        assert "220.5" in snapshot.total_points_odds
        assert snapshot.total_points_odds["220.5"]["over"] == pytest.approx(1.90)
        assert snapshot.total_points_odds["220.5"]["under"] == pytest.approx(1.90)

    def test_parse_inplay_minute(self):
        payload = _basket_event_payload()
        snapshot = parse_superbet_event(payload)
        assert snapshot.inplay is not None
        assert snapshot.inplay.home_score == 50
        assert snapshot.inplay.away_score == 45
        assert snapshot.inplay.minute == 24
