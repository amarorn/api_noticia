"""Testes do parser de beisebol Superbet."""
from __future__ import annotations

from ingest.superbet.parser import parse_superbet_event


def test_parse_baseball_inning_and_moneyline():
    ev = {
        "event_id": 1,
        "fixture": {
            "event_id": 1,
            "event_name": "Hanwha Eagles·Kiwoom Heroes",
            "sport_id": 20,
            "event_tags": "superLive",
        },
        "inplay_stats": {
            "home_team_score": "0",
            "away_team_score": "5",
            "periods": [
                {"num": 1, "home_team_score": "0", "away_team_score": "1", "type": 1},
                {"num": 5, "home_team_score": "0", "away_team_score": "2", "type": 1},
            ],
            "team_serving": 1,
        },
        "inplay_stats_metadata": {
            "event_status_label": "5I",
            "period_status": "5I",
            "status": "STARTED",
        },
        "markets": [
            {
                "name": "Vencedor (incl. entradas extras)",
                "odds": [
                    {"price": 8.5, "status": 1, "metadata": {"code": "1", "name": "Hanwha Eagles"}},
                    {"price": 1.04, "status": 1, "metadata": {"code": "2", "name": "Kiwoom Heroes"}},
                ],
            },
            {
                "name": "Handicap (incl. entradas extras)",
                "odds": [
                    {
                        "price": 1.78,
                        "status": 1,
                        "metadata": {
                            "code": "1",
                            "name": "Hanwha Eagles",
                            "special_bet_value": "+4.5",
                        },
                    },
                    {
                        "price": 1.92,
                        "status": 1,
                        "metadata": {
                            "code": "2",
                            "name": "Kiwoom Heroes",
                            "special_bet_value": "-4.5",
                        },
                    },
                ],
            },
            {
                "name": "Hanwha Eagles - Total de Corridas (incl. entradas extras)",
                "odds": [
                    {"price": 1.90, "status": 1, "metadata": {"code": "+", "name": "Mais", "special_bet_value": "3.5"}},
                    {"price": 1.90, "status": 1, "metadata": {"code": "-", "name": "Menos", "special_bet_value": "3.5"}},
                ],
            },
            {
                "name": "Kiwoom Heroes - Total de Corridas (incl. entradas extras)",
                "odds": [
                    {"price": 1.90, "status": 1, "metadata": {"code": "+", "name": "Mais", "special_bet_value": "5.5"}},
                    {"price": 1.90, "status": 1, "metadata": {"code": "-", "name": "Menos", "special_bet_value": "5.5"}},
                ],
            },
        ],
    }
    snap = parse_superbet_event(ev)
    assert snap.inplay is not None
    assert snap.inplay.minute == 5
    assert snap.inplay.period_label == "5I"
    assert snap.inplay.home_score == 0
    assert snap.inplay.away_score == 5
    assert len(snap.inplay.baseball_innings) == 2
    assert snap.moneyline_odds["1"] == 8.5
    assert snap.moneyline_odds["2"] == 1.04
    assert snap.sport_id == 20
    assert snap.total_points_odds == {}
    assert snap.inferred_total_runs == 9.0
    assert snap.spread_odds
