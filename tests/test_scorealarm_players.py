from tests.fixtures.scorealarm_samples import PLAYER_STATS_SSE
from ingest.superbet.scorealarm.players import build_top_players, parse_player_stats_sse
from ingest.superbet.scorealarm.social import fetch_social_top_picks


def test_parse_player_stats_sse_maps_goals_and_saves():
    players = parse_player_stats_sse(
        PLAYER_STATS_SSE,
        home_team="Colômbia",
        away_team="Jordânia",
    )
    assert len(players) == 3
    scorer = next(p for p in players if p["name"] == "J. Quintero")
    assert scorer["stats"]["goals"] == 1
    assert scorer["stats"]["shots_on_target"] == 2
    assert scorer["team"] == "Colômbia"
    assert scorer["position_label"] == "ATA"


def test_build_top_players_ranks_by_activity():
    players = parse_player_stats_sse(
        PLAYER_STATS_SSE,
        home_team="Colômbia",
        away_team="Jordânia",
    )
    top = build_top_players(players, limit=3)
    assert len(top) == 2
    assert top[0]["name"] == "J. Quintero"
    assert "gol" in top[0]["highlights"][0]


def test_fetch_social_top_picks_disabled_by_default(monkeypatch):
    monkeypatch.setattr(
        "ingest.superbet.scorealarm.social.settings.social_top_picks_enabled",
        False,
    )
    result = fetch_social_top_picks("ax:match:13127506", event_id=13127506)
    assert result["available"] is False
    assert result["picks"] == []
