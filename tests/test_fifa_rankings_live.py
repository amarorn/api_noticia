from __future__ import annotations

from ingest.fifa.rankings_live import (
    FifaRankingEntry,
    extract_rankings_from_window,
    get_team_points_live,
)


def test_extract_rankings_from_window_basic():
    matches = [
        {
            "Home": {
                "IdTeam": "43924",
                "IdCountry": "BRA",
                "TeamName": [{"Locale": "en-GB", "Description": "Brazil"}],
            },
            "Away": {
                "IdTeam": "43914",
                "IdCountry": "PAN",
                "TeamName": [{"Locale": "en-GB", "Description": "Panama"}],
            },
            "TeamAId": "43924",
            "TeamBId": "43914",
            "TeamAPoints": 1762.66,
            "TeamAPointsBefore": 1761.16,
            "TeamBPoints": 1539.14,
            "TeamBPointsBefore": 1540.64,
        }
    ]
    rankings = extract_rankings_from_window(matches)
    assert "43924" in rankings
    assert "43914" in rankings
    assert rankings["43924"].points == 1762.66
    assert rankings["43924"].points_before == 1761.16
    assert rankings["43924"].country_code == "BRA"


def test_get_team_points_live_by_code():
    rankings = {
        "43924": FifaRankingEntry(
            team_id="43924",
            country_code="BRA",
            team_name="Brazil",
            points=1762.66,
            points_before=1761.16,
        )
    }
    points = get_team_points_live("BRA", rankings)
    assert points == 1762.66


def test_get_team_points_live_by_name():
    rankings = {
        "43924": FifaRankingEntry(
            team_id="43924",
            country_code="BRA",
            team_name="Brazil",
            points=1762.66,
            points_before=1761.16,
        )
    }
    points = get_team_points_live("Brasil", rankings)
    assert points == 1762.66


def test_get_team_points_live_not_found():
    rankings = {}
    points = get_team_points_live("Inexistente", rankings)
    assert points is None
