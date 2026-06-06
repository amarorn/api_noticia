from __future__ import annotations

from ingest.fifa.match_ingest import (
    FifaMatchDetails,
    FifaTeamLineup,
    _extract_name,
    _parse_bookings,
    _parse_goals,
    _parse_players,
    _parse_substitutions,
)


def test_extract_name_pt_priority():
    names = [
        {"Locale": "pt-BR", "Description": "Brasil"},
        {"Locale": "en-GB", "Description": "Brazil"},
    ]
    assert _extract_name(names) == "Brasil"


def test_extract_name_fallback_en():
    names = [{"Locale": "en-GB", "Description": "Germany"}]
    assert _extract_name(names) == "Germany"


def test_extract_name_empty():
    assert _extract_name([]) == ""


def test_parse_goals_basic():
    raw = [
        {
            "Type": 2,
            "IdPlayer": "123",
            "Minute": "15'",
            "IdAssistPlayer": "456",
            "Period": 3,
        }
    ]
    goals = _parse_goals(raw, "BRA")
    assert len(goals) == 1
    assert goals[0].minute == "15'"
    assert goals[0].player_id == "123"
    assert goals[0].goal_type == 2
    assert goals[0].period == 3


def test_parse_bookings_yellow():
    raw = [
        {
            "Card": 1,
            "Period": 3,
            "IdPlayer": "789",
            "PlayerName": [{"Locale": "en-GB", "Description": "Neymar"}],
            "Minute": "30'",
            "Reason": "Foul",
        }
    ]
    bookings = _parse_bookings(raw, "BRA")
    assert len(bookings) == 1
    assert bookings[0].card_type == 1
    assert bookings[0].player_name == "Neymar"
    assert bookings[0].reason == "Foul"


def test_parse_substitutions():
    raw = [
        {
            "Minute": "70'",
            "IdPlayerOff": "111",
            "PlayerOffName": [{"Locale": "en-GB", "Description": "Coutinho"}],
            "IdPlayerOn": "222",
            "PlayerOnName": [{"Locale": "en-GB", "Description": "Firmino"}],
            "Period": 5,
        }
    ]
    subs = _parse_substitutions(raw)
    assert len(subs) == 1
    assert subs[0].minute == "70'"
    assert subs[0].player_off_name == "Coutinho"
    assert subs[0].player_on_name == "Firmino"


def test_parse_players():
    raw = [
        {
            "IdPlayer": "p1",
            "ShirtNumber": 10,
            "Position": 3,
            "Captain": True,
            "Status": 1,
            "FieldStatus": 1,
            "PlayerName": [{"Locale": "en-GB", "Description": "Messi"}],
            "ShortName": [{"Locale": "en-GB", "Description": "L. Messi"}],
            "PlayerPicture": {"PictureUrl": "http://pic.com/messi"},
        }
    ]
    players = _parse_players(raw)
    assert len(players) == 1
    assert players[0].id == "p1"
    assert players[0].shirt_number == 10
    assert players[0].position == 3
    assert players[0].is_captain is True
    assert players[0].picture_url == "http://pic.com/messi"


def test_fifa_match_details_to_dict():
    lineup = FifaTeamLineup(
        team_id="BRA",
        team_name="Brazil",
        country_code="BRA",
        score=2,
        tactics="4-3-3",
        coach="Dorival",
        players=[],
        goals=[],
        bookings=[],
        substitutions=[],
    )
    details = FifaMatchDetails(
        match_id="m1",
        date="2026-06-15",
        competition="World Cup",
        season="2026",
        stage="Group",
        group="A",
        stadium="Maracanã",
        city="Rio",
        attendance=70000,
        home_team=lineup,
        away_team=lineup,
        winner_id="BRA",
        match_status=100,
        period=10,
    )
    d = details.to_dict()
    assert d["match_id"] == "m1"
    assert d["home_team"]["team_name"] == "Brazil"
    assert d["home_team"]["tactics"] == "4-3-3"
