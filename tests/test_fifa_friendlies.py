from ingest.fifa.friendlies import (
    is_fifa_friendly_match,
    list_fifa_team_friendlies,
    map_fifa_window_match,
)
from ingest.sofascore.friendlies import FriendlyMatch, merge_friendlies


def _fifa_window_match(
    *,
    match_id: str = "1001",
    home_code: str = "BRA",
    away_code: str = "EGY",
    home_name: str = "Brazil",
    away_name: str = "Egypt",
    date: str = "2026-06-06T22:00:00Z",
    period: int = 0,
) -> dict:
    return {
        "IdMatch": match_id,
        "Date": date,
        "Period": period,
        "SeasonName": [{"Locale": "en", "Description": "Friendly 2026"}],
        "Home": {"IdCountry": home_code, "TeamName": [{"Locale": "en", "Description": home_name}]},
        "Away": {"IdCountry": away_code, "TeamName": [{"Locale": "en", "Description": away_name}]},
    }


def test_is_fifa_friendly_match():
    assert is_fifa_friendly_match(_fifa_window_match())
    assert not is_fifa_friendly_match(
        {"SeasonName": [{"Description": "World Cup 2026"}], "Home": {}, "Away": {}}
    )


def test_map_fifa_window_match_for_brazil():
    mapped = map_fifa_window_match(_fifa_window_match(), team="Brasil")
    assert mapped is not None
    assert mapped.home_team == "Brasil"
    assert mapped.away_team == "Egito"
    assert mapped.fifa_match_id == "1001"
    assert mapped.sources == ("fifa",)


def test_list_fifa_team_friendlies_filters_year():
    window = [
        _fifa_window_match(match_id="1", date="2026-06-06T22:00:00Z"),
        _fifa_window_match(match_id="2", date="2025-03-01T22:00:00Z"),
    ]
    rows = list_fifa_team_friendlies("Brasil", year=2026, matches=window)
    assert len(rows) == 1
    assert rows[0].fifa_match_id == "1"


def test_merge_friendlies_enriches_sofascore_with_fifa_id():
    sofascore = FriendlyMatch(
        home_team="Brasil",
        away_team="Egito",
        match_date="2026-06-06T22:00:00+00:00",
        status="notstarted",
        home_score=None,
        away_score=None,
        tournament="Int. Friendly Games",
        is_home=True,
        event_id=99,
        sources=("sofascore",),
    )
    fifa = FriendlyMatch(
        home_team="Brasil",
        away_team="Egito",
        match_date="2026-06-06T22:00:00Z",
        status="notstarted",
        home_score=None,
        away_score=None,
        tournament="Friendly 2026",
        is_home=True,
        fifa_match_id="1001",
        sources=("fifa",),
    )
    merged = merge_friendlies([sofascore], [fifa])
    assert len(merged) == 1
    assert merged[0].event_id == 99
    assert merged[0].fifa_match_id == "1001"
    assert set(merged[0].sources) == {"sofascore", "fifa"}
