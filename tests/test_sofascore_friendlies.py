from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from ingest.sofascore.friendlies import (
    FriendlyMatch,
    is_friendly_event,
    list_team_friendlies,
    load_friendlies_snapshot,
    map_friendly_event,
    match_year,
    save_friendlies_snapshot,
)


def _no_fifa_friendlies(*_args, **_kwargs):
    return []


def _friendly_event(
    *,
    event_id: int,
    home_id: int = 4748,
    away_id: int = 4701,
    home_name: str = "Brazil",
    away_name: str = "Argentina",
    timestamp: int = 1_700_000_000,
    status_type: str = "finished",
    status_code: int = 100,
    home_score: int | None = 2,
    away_score: int | None = 1,
) -> dict:
    return {
        "id": event_id,
        "startTimestamp": timestamp,
        "status": {"type": status_type, "code": status_code},
        "homeTeam": {"id": home_id, "name": home_name},
        "awayTeam": {"id": away_id, "name": away_name},
        "homeScore": {"current": home_score},
        "awayScore": {"current": away_score},
        "tournament": {"name": "Int. Friendly Games", "slug": "international-friendly"},
    }


TEAM_MAP = {
    "Brasil": {"sofascore_id": 4748, "sofascore_name": "Brazil"},
    "Argentina": {"sofascore_id": 4701, "sofascore_name": "Argentina"},
}


def test_is_friendly_event_by_slug():
    assert is_friendly_event({"tournament": {"slug": "international-friendly"}})
    assert not is_friendly_event({"tournament": {"slug": "world-championship"}})


def test_map_friendly_event_for_home_team():
    event = _friendly_event(event_id=99)
    mapped = map_friendly_event(event, team="Brasil", team_map=TEAM_MAP)
    assert mapped is not None
    assert mapped.event_id == 99
    assert mapped.home_team == "Brasil"
    assert mapped.away_team == "Argentina"
    assert mapped.is_home is True
    assert mapped.status == "finished"
    assert mapped.home_score == 2


@patch("ingest.fifa.friendlies.list_fifa_team_friendlies", side_effect=_no_fifa_friendlies)
def test_list_team_friendlies_filters_and_sorts(_mock_fifa):
    ts_jan = int(datetime(2024, 1, 10, 20, 0, tzinfo=timezone.utc).timestamp())
    ts_jun = int(datetime(2024, 6, 10, 20, 0, tzinfo=timezone.utc).timestamp())
    client = MagicMock()
    client.team_upcoming_events.return_value = []
    client.team_recent_events.return_value = [
        _friendly_event(event_id=1, timestamp=ts_jan),
        _friendly_event(event_id=2, timestamp=ts_jun, status_type="notstarted", status_code=0),
        {
            "id": 3,
            "startTimestamp": 1_720_000_000,
            "status": {"type": "finished", "code": 100},
            "homeTeam": {"id": 4748, "name": "Brazil"},
            "awayTeam": {"id": 4701, "name": "Argentina"},
            "tournament": {"slug": "world-championship"},
        },
    ]

    friendlies = list_team_friendlies(
        "Brasil",
        pages=1,
        year=2024,
        client=client,
        team_map=TEAM_MAP,
    )

    assert len(friendlies) == 2
    assert friendlies[0].event_id == 2
    assert friendlies[1].event_id == 1


@patch("ingest.fifa.friendlies.list_fifa_team_friendlies", side_effect=_no_fifa_friendlies)
def test_list_team_friendlies_includes_upcoming_from_next_endpoint(_mock_fifa):
    ts_today = int(datetime(2026, 6, 6, 20, 0, tzinfo=timezone.utc).timestamp())
    client = MagicMock()
    client.team_upcoming_events.return_value = [
        _friendly_event(event_id=99, timestamp=ts_today, status_type="notstarted", status_code=0),
    ]
    client.team_recent_events.return_value = []

    friendlies = list_team_friendlies(
        "Brasil",
        pages=1,
        upcoming_pages=1,
        year=2026,
        client=client,
        team_map=TEAM_MAP,
    )

    assert len(friendlies) == 1
    assert friendlies[0].event_id == 99
    assert friendlies[0].status == "notstarted"


@patch("ingest.fifa.friendlies.list_fifa_team_friendlies", side_effect=_no_fifa_friendlies)
def test_list_team_friendlies_filters_by_year(_mock_fifa):
    ts_2026 = int(datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc).timestamp())
    ts_2025 = int(datetime(2025, 3, 1, 20, 0, tzinfo=timezone.utc).timestamp())
    client = MagicMock()
    client.team_upcoming_events.return_value = []
    client.team_recent_events.return_value = [
        _friendly_event(event_id=10, timestamp=ts_2026),
        _friendly_event(event_id=11, timestamp=ts_2025),
    ]

    friendlies = list_team_friendlies(
        "Brasil",
        pages=1,
        year=2026,
        client=client,
        team_map=TEAM_MAP,
    )

    assert len(friendlies) == 1
    assert friendlies[0].event_id == 10
    assert match_year(friendlies[0].match_date) == 2026


def test_save_and_load_friendlies_snapshot(tmp_path):
    rows = [
        FriendlyMatch(
            home_team="Brasil",
            away_team="Egito",
            match_date="2026-06-06T22:00:00+00:00",
            status="notstarted",
            home_score=None,
            away_score=None,
            tournament="Int. Friendly Games",
            is_home=True,
            event_id=1,
        )
    ]
    save_friendlies_snapshot("Brasil", 2026, rows, output_dir=tmp_path)
    loaded = load_friendlies_snapshot("Brasil", 2026, output_dir=tmp_path)
    assert loaded is not None
    assert len(loaded) == 1
    assert loaded[0].away_team == "Egito"
