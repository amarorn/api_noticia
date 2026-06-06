from datetime import date
from unittest.mock import MagicMock, patch

from ingest.sofascore.friendlies import FriendlyMatch
from models.wc_match_simulator import _resolve_sofascore_context


def test_resolve_sofascore_context_uses_event_id_from_url():
    client = MagicMock()
    client.event.return_value = {
        "startTimestamp": 1_748_745_600,
        "homeTeam": {"id": 1, "name": "Brazil"},
        "awayTeam": {"id": 2, "name": "Egypt"},
    }

    event_id, match_day = _resolve_sofascore_context(
        "Brasil",
        "Egito",
        sofascore_event_id=12345,
        match_date=None,
        phase="round_16",
        client=client,
    )

    assert event_id == 12345
    assert match_day is not None


@patch("ingest.sofascore.friendlies.list_team_friendlies")
def test_resolve_sofascore_context_falls_back_to_friendlies(mock_list):
    mock_list.return_value = [
        FriendlyMatch(
            home_team="Brasil",
            away_team="Egito",
            match_date="2026-06-06T22:00:00+00:00",
            status="notstarted",
            home_score=None,
            away_score=None,
            tournament="Int. Friendly Games",
            is_home=True,
            event_id=998877,
        )
    ]

    event_id, match_day = _resolve_sofascore_context(
        "Brasil",
        "Egito",
        sofascore_event_id=None,
        match_date=None,
        phase="round_16",
        client=MagicMock(),
    )

    assert event_id == 998877
    assert match_day == date(2026, 6, 6)


def test_resolve_sofascore_context_keeps_explicit_match_date():
    event_id, match_day = _resolve_sofascore_context(
        "Brasil",
        "Egito",
        sofascore_event_id=None,
        match_date=date(2026, 6, 6),
        phase="round_16",
        client=MagicMock(),
    )

    assert event_id is None
    assert match_day == date(2026, 6, 6)
