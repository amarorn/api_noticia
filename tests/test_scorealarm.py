from tests.fixtures.scorealarm_samples import OVERVIEW_STATISTICS, TEAM_STATS_SSE
from ingest.superbet.scorealarm.stat_types import (
    merge_live_stats,
    parse_overview_statistics,
    parse_team_stats_sse,
)
from ingest.superbet.scorealarm.ticker import parse_timeline_events


def test_parse_overview_statistics_possession_and_corners():
    stats = parse_overview_statistics(OVERVIEW_STATISTICS, period=0)
    assert stats["home_possession_pct"] == 49.0
    assert stats["away_possession_pct"] == 51.0
    assert stats["home_corners"] == 3.0
    assert stats["away_corners"] == 3.0
    assert stats["home_yellow_cards"] == 2.0
    assert stats["away_yellow_cards"] == 0.0


def test_parse_team_stats_sse_shots_and_cards():
    stats = parse_team_stats_sse(TEAM_STATS_SSE)
    assert stats["home_shots"] == 1.0
    assert stats["away_shots"] == 5.0
    assert stats["home_shots_on_target"] == 1.0
    assert stats["away_shots_on_target"] == 4.0
    assert stats["home_yellow_cards"] == 2.0
    assert stats["away_yellow_cards"] == 0.0


def test_merge_live_stats_prefers_overview_possession():
    overview = parse_overview_statistics(OVERVIEW_STATISTICS)
    sse = parse_team_stats_sse(TEAM_STATS_SSE)
    merged = merge_live_stats(overview, sse)
    assert merged["home_possession_pct"] == 49.0
    assert merged["away_shots_on_target"] == 4.0


def test_parse_timeline_events_goal_and_corner():
    rows = parse_timeline_events(
        OVERVIEW_STATISTICS["live_events"],
        home_team="Nosaby IF",
        away_team="Lilla Torg FF",
    )
    assert len(rows) == 2
    assert rows[0]["minute"] == 24
    assert rows[0]["label"] == "Escanteio"
    goal = next(r for r in rows if r["type"] == 4)
    assert goal["team"] == "Lilla Torg FF"
    assert goal["icon"] == "⚽"
