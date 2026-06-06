from unittest.mock import MagicMock, patch

from ingest.sofascore.history_ingest import ingest_team_history


def test_ingest_team_history_skips_finished_and_existing():
    client = MagicMock()
    client.team_recent_events.return_value = [
        {"id": 1, "status": {"type": "finished", "code": 100}},
        {"id": 2, "status": {"type": "notstarted"}},
        {"id": 3, "status": {"type": "finished", "code": 100}},
    ]
    team_map = {"Brasil": {"id": 4748, "name": "Brazil"}}

    with (
        patch("ingest.sofascore.history_ingest._existing_event_ids", return_value={1}),
        patch("ingest.sofascore.history_ingest.ingest_match_stats") as ingest_mock,
        patch(
            "ingest.sofascore.history_ingest.resolve_team_id",
            return_value=(4748, team_map["Brasil"]),
        ),
    ):
        ok, skip, fail = ingest_team_history(
            "Brasil",
            max_events=10,
            client=client,
            team_map=team_map,
            save=False,
        )

    assert ok == 1
    assert skip == 2
    assert fail == 0
    ingest_mock.assert_called_once_with(event_id=3, save=False)
