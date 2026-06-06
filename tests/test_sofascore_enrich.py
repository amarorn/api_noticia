from __future__ import annotations


import pytest

from ingest.sofascore.enrich_mapper import (
    flatten_enrich_features,
    map_h2h,
    map_incidents_extended,
    map_pregame_form,
    map_team_streaks,
)
from ingest.sofascore.enrich import build_enrich_payload


class FakeEnrichClient:
    def __init__(
        self,
        event: dict,
        pregame_form: dict | None,
        team_streaks: dict | None,
        h2h: dict | None,
        incidents: dict | None,
    ):
        self._event = event
        self._pregame_form = pregame_form
        self._team_streaks = team_streaks
        self._h2h = h2h
        self._incidents = incidents

    def event(self, event_id: int) -> dict:
        return self._event

    def event_pregame_form(self, event_id: int) -> dict:
        if self._pregame_form is None:
            raise RuntimeError("no pregame form")
        return self._pregame_form

    def event_team_streaks(self, event_id: int) -> dict:
        if self._team_streaks is None:
            raise RuntimeError("no team streaks")
        return self._team_streaks

    def event_h2h(self, event_id: int) -> dict:
        if self._h2h is None:
            raise RuntimeError("no h2h")
        return self._h2h

    def event_incidents(self, event_id: int) -> dict:
        if self._incidents is None:
            raise RuntimeError("no incidents")
        return self._incidents


def test_map_pregame_form_basic():
    payload = {
        "homeTeam": {
            "position": 1,
            "value": 25,
            "avgRating": 7.2,
            "form": ["W", "W", "D", "L", "W"],
        },
        "awayTeam": {
            "position": 5,
            "value": 15,
            "avgRating": 6.8,
            "form": ["L", "D", "D", "W", "L"],
        },
    }
    mapped = map_pregame_form(payload)
    assert mapped["home_position_competition"] == 1
    assert mapped["away_position_competition"] == 5
    assert mapped["home_points_competition"] == 25
    assert mapped["away_points_competition"] == 15
    assert mapped["home_avgrating_last5"] == 7.2
    assert mapped["away_avgrating_last5"] == 6.8
    assert mapped["home_form_points_last5"] == 10  # 3+3+1+0+3
    assert mapped["away_form_points_last5"] == 5   # 0+1+1+3+0
    assert mapped["home_form_wins_last5"] == 3
    assert mapped["away_form_wins_last5"] == 1
    assert mapped["position_diff"] == -4  # 1 - 5
    assert mapped["points_diff"] == 10    # 25 - 15
    assert mapped["form_points_diff"] == 5  # 10 - 5


def test_map_pregame_form_empty_form():
    payload = {
        "homeTeam": {"position": 3, "value": 10, "avgRating": 6.5},
        "awayTeam": {"position": 8, "value": 5, "avgRating": 6.0},
    }
    mapped = map_pregame_form(payload)
    # Quando não há form, as métricas de form não são adicionadas
    assert "home_form_points_last5" not in mapped
    assert mapped["position_diff"] == -5


def test_map_team_streaks_unbeaten_and_wins():
    payload = {
        "general": [
            {"team": "home", "name": "Unbeaten", "value": 8, "continued": True},
            {"team": "away", "name": "Wins", "value": 3, "continued": True},
            {"team": "home", "name": "Clean sheets", "value": 4, "continued": False},
        ]
    }
    mapped = map_team_streaks(payload)
    assert mapped["home_streak_unbeaten"] == 8
    assert mapped["away_streak_wins"] == 3
    assert mapped["home_streak_clean_sheets"] == 4
    assert mapped["home_streak_continued"] == 0  # último streak do home tem continued=False
    assert mapped["streak_unbeaten_diff"] == 8   # 8 - 0
    assert mapped["streak_wins_diff"] == -3      # 0 - 3


def test_map_h2h_basic():
    payload = {
        "teamDuel": {
            "homeWins": 10,
            "awayWins": 5,
            "draws": 3,
        },
        "matches": [
            {"winnerCode": "1"},
            {"winnerCode": "3"},
            {"winnerCode": "2"},
            {"winnerCode": "1"},
            {"winnerCode": "1"},
        ],
    }
    mapped = map_h2h(payload)
    assert mapped["h2h_home_wins_all"] == 10
    assert mapped["h2h_away_wins_all"] == 5
    assert mapped["h2h_draws_all"] == 3
    assert mapped["h2h_total_all"] == 18
    assert mapped["h2h_home_win_rate"] == pytest.approx(10 / 18, abs=0.001)
    assert mapped["h2h_home_wins_recent5"] == 3
    assert mapped["h2h_away_wins_recent5"] == 1
    assert mapped["h2h_draws_recent5"] == 1


def test_map_h2h_empty():
    mapped = map_h2h({})
    assert mapped["h2h_total_all"] == 0
    assert mapped["h2h_home_win_rate"] == 0.0


def test_map_incidents_extended_temporal():
    payload = {
        "incidents": [
            {"incidentType": "goal", "isHome": True, "time": 15},
            {"incidentType": "goal", "isHome": False, "time": 35},
            {"incidentType": "goal", "isHome": True, "time": 55},
            {"incidentType": "goal", "isHome": False, "time": 75},
            {"incidentType": "card", "incidentClass": "red", "isHome": True, "time": 45},
        ]
    }
    mapped = map_incidents_extended(payload)
    assert mapped["incident_first_goal_minute"] == 15
    assert mapped["incident_goals_ht_home"] == 1  # só o de 15 (55 é > 45)
    assert mapped["incident_goals_ht_away"] == 1  # 35
    assert mapped["incident_goals_ft_home"] == 1  # 55
    assert mapped["incident_goals_ft_away"] == 1  # 75
    assert mapped["incident_red_cards_before_60_home"] == 1  # 45 < 60
    assert mapped["incident_red_cards_before_60_away"] == 0


def test_flatten_enrich_features_combined():
    row = flatten_enrich_features(
        event_id=99,
        home_team="Brasil",
        away_team="Argentina",
        match_date="2026-06-15",
        pregame_form={
            "homeTeam": {"position": 1, "value": 30, "avgRating": 7.5, "form": ["W", "W", "W", "W", "W"]},
            "awayTeam": {"position": 2, "value": 25, "avgRating": 7.0, "form": ["W", "W", "D", "W", "L"]},
        },
        team_streaks={"general": [{"team": "home", "name": "Unbeaten", "value": 10, "continued": True}]},
        h2h={"teamDuel": {"homeWins": 5, "awayWins": 3, "draws": 2}},
        incidents=None,
    )
    assert row["event_id"] == 99
    assert row["home_team"] == "Brasil"
    assert row["away_team"] == "Argentina"
    assert row["home_form_win_pct_last5"] == 1.0
    assert row["away_form_win_pct_last5"] == 0.6
    assert row["home_streak_unbeaten"] == 10
    assert row["h2h_total_all"] == 10


def test_build_enrich_payload_with_event_id():
    team_map = {
        "Brasil": {"sofascore_id": 4748},
        "Argentina": {"sofascore_id": 4819},
    }
    event = {
        "id": 42,
        "homeTeam": {"id": 4748, "name": "Brazil"},
        "awayTeam": {"id": 4819, "name": "Argentina"},
    }
    pregame_form = {
        "homeTeam": {"position": 1, "value": 20, "avgRating": 7.0, "form": ["W", "D", "W"]},
        "awayTeam": {"position": 3, "value": 12, "avgRating": 6.5, "form": ["L", "W", "D"]},
    }
    team_streaks = {"general": []}
    h2h = {"teamDuel": {"homeWins": 2, "awayWins": 1, "draws": 1}}
    incidents = {"incidents": []}

    client = FakeEnrichClient(event, pregame_form, team_streaks, h2h, incidents)
    result = build_enrich_payload(
        event_id=42,
        client=client,
        team_map=team_map,
    )
    assert result.home_team == "Brasil"
    assert result.away_team == "Argentina"
    assert result.features["home_position_competition"] == 1
    assert result.features["away_position_competition"] == 3
