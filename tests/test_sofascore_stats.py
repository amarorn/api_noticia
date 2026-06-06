from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingest.sofascore.stats_mapper import (
    flatten_match_stats,
    map_event_incidents,
    map_event_statistics,
)
from ingest.sofascore.stats_ingest import (
    build_match_stats_payload,
    upsert_match_stats_parquet,
)


class FakeStatsClient:
    def __init__(self, event: dict, statistics: dict, incidents: dict):
        self._event = event
        self._statistics = statistics
        self._incidents = incidents

    def event(self, event_id: int) -> dict:
        return self._event

    def event_statistics(self, event_id: int) -> dict:
        return self._statistics

    def event_incidents(self, event_id: int) -> dict:
        return self._incidents


def test_map_event_statistics_corners_and_possession():
    payload = {
        "statistics": [
            {
                "period": "ALL",
                "groups": [
                    {
                        "groupName": "Match overview",
                        "statisticsItems": [
                            {
                                "name": "Ball possession",
                                "key": "ballPossession",
                                "home": "58%",
                                "away": "42%",
                                "homeValue": 58,
                                "awayValue": 42,
                            },
                            {
                                "name": "Corner kicks",
                                "key": "cornerKicks",
                                "home": "7",
                                "away": "3",
                                "homeValue": 7,
                                "awayValue": 3,
                            },
                            {
                                "name": "Expected goals",
                                "key": "expectedGoals",
                                "home": "1.84",
                                "away": "0.53",
                                "homeValue": 1.84,
                                "awayValue": 0.53,
                            },
                        ],
                    }
                ],
            }
        ]
    }
    mapped = map_event_statistics(payload)
    assert mapped["home_possession_pct"] == 58.0
    assert mapped["away_possession_pct"] == 42.0
    assert mapped["home_corners"] == 7.0
    assert mapped["away_corners"] == 3.0
    assert mapped["home_xg"] == 1.84
    assert mapped["away_xg"] == 0.53


def test_map_event_incidents_summary():
    payload = {
        "incidents": [
            {"incidentType": "goal", "isHome": True},
            {"incidentType": "goal", "isHome": False},
            {"incidentType": "card", "incidentClass": "yellow", "isHome": True},
            {"incidentType": "card", "incidentClass": "red", "isHome": False},
            {"incidentType": "substitution", "isHome": True},
        ]
    }
    mapped = map_event_incidents(payload)
    assert mapped["incident_goals_home"] == 1
    assert mapped["incident_goals_away"] == 1
    assert mapped["incident_yellow_cards_home"] == 1
    assert mapped["incident_red_cards_away"] == 1
    assert mapped["incident_substitutions_home"] == 1


def test_build_match_stats_payload_with_event_id():
    team_map = {
        "Brasil": {"sofascore_id": 4748},
        "Argentina": {"sofascore_id": 4819},
    }
    event = {
        "id": 42,
        "homeTeam": {"id": 4748, "name": "Brazil"},
        "awayTeam": {"id": 4819, "name": "Argentina"},
    }
    statistics = {
        "statistics": [
            {
                "period": "ALL",
                "groups": [
                    {
                        "statisticsItems": [
                            {
                                "name": "Total shots",
                                "homeValue": 12,
                                "awayValue": 8,
                            }
                        ]
                    }
                ],
            }
        ]
    }
    incidents = {"incidents": []}
    client = FakeStatsClient(event, statistics, incidents)
    result = build_match_stats_payload(
        event_id=42,
        client=client,
        team_map=team_map,
    )
    assert result.home_team == "Brasil"
    assert result.away_team == "Argentina"
    assert result.stats["home_shots_total"] == 12.0
    assert result.stats["away_shots_total"] == 8.0


def test_upsert_match_stats_parquet_dedup(tmp_path: Path):
    row_a = flatten_match_stats(
        event_id=1,
        home_team="Brasil",
        away_team="Argentina",
        match_date="2026-06-10",
        statistics_payload={
            "statistics": [
                {
                    "period": "ALL",
                    "groups": [
                        {
                            "statisticsItems": [
                                {
                                    "name": "Corner kicks",
                                    "homeValue": 4,
                                    "awayValue": 2,
                                }
                            ]
                        }
                    ],
                }
            ]
        },
        incidents_payload=None,
    )
    row_b = {**row_a, "home_corners": 9.0}
    upsert_match_stats_parquet(row_a, output_dir=tmp_path)
    path = upsert_match_stats_parquet(row_b, output_dir=tmp_path)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert float(df.iloc[0]["home_corners"]) == 9.0
