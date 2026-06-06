import json
from unittest.mock import MagicMock, patch

from ingest.fifa.match_ingest import load_fifa_window_matches


def test_load_fifa_window_matches_uses_stale_cache_on_network_error(tmp_path, monkeypatch):
    cache_path = tmp_path / "window_matches.json"
    cache_path.write_text(
        json.dumps({"matches": [{"IdMatch": "1", "Date": "2026-01-01T00:00:00Z"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("ingest.fifa.match_ingest.settings.fifa_window_cache_path", cache_path)

    client = MagicMock()
    client.match_window_matches.side_effect = ConnectionError("offline")

    matches = load_fifa_window_matches(client=client, force_refresh=True)
    assert len(matches) == 1
    assert matches[0]["IdMatch"] == "1"


@patch("ingest.fifa.friendlies.load_fifa_window_matches", side_effect=ConnectionError("offline"))
def test_list_fifa_team_friendlies_returns_empty_when_window_unavailable(_mock_window):
    from ingest.fifa.friendlies import list_fifa_team_friendlies

    rows = list_fifa_team_friendlies("Brasil", year=2026)
    assert rows == []
