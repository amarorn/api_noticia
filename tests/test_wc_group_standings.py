from datetime import UTC, datetime, timedelta

import pandas as pd

from pipelines.wc_group_standings import (
    build_group_standings,
    build_group_standings_from_results,
    load_wc_group_results,
    merge_real_into_simulated,
)


def test_build_group_standings_points():
    groups = [{"id": "C", "teams": ["Brasil", "Marrocos", "Haiti", "Escócia"]}]
    preds = [
        {"home_team": "Brasil", "away_team": "Marrocos", "prediction": "1", "group": "C"},
        {"home_team": "Brasil", "away_team": "Haiti", "prediction": "1", "group": "C"},
        {"home_team": "Escócia", "away_team": "Brasil", "prediction": "2", "group": "C"},
    ]
    blocks = build_group_standings(groups, preds)
    assert len(blocks) == 1
    brasil = next(r for r in blocks[0]["standings"] if r["team"] == "Brasil")
    assert brasil["points"] == 9
    assert brasil["won"] == 3
    assert brasil["position"] == 1


def test_build_group_standings_from_real_scores():
    groups = [{"id": "C", "teams": ["Brasil", "Marrocos", "Haiti", "Escócia"]}]
    results = [
        {"home_team": "Brasil", "away_team": "Marrocos", "home_score": 2, "away_score": 1, "group": "C"},
        {"home_team": "Brasil", "away_team": "Haiti", "home_score": 1, "away_score": 1, "group": "C"},
    ]
    blocks = build_group_standings_from_results(groups, results)
    brasil = next(r for r in blocks[0]["standings"] if r["team"] == "Brasil")
    marrocos = next(r for r in blocks[0]["standings"] if r["team"] == "Marrocos")
    assert brasil["points"] == 4
    assert brasil["played"] == 2
    assert brasil["gd"] == 1
    assert marrocos["points"] == 0


def test_merge_real_into_simulated():
    sim = [{"group": "C", "standings": [{"team": "Brasil", "points": 9, "position": 1}]}]
    real = [{"group": "C", "standings": [{"team": "Brasil", "points": 4, "played": 2, "gd": 1}]}]
    merged = merge_real_into_simulated(sim, real)
    row = merged[0]["standings"][0]
    assert row["points"] == 9
    assert row["real_points"] == 4
    assert row["real_played"] == 2
    assert row["real_gd"] == 1


def test_load_wc_group_results_from_round_file():
    round_data = {
        "season": 2026,
        "phase": "group",
        "groups": [{"id": "C", "teams": ["Brasil", "Marrocos"]}],
        "matches": [
            {
                "home_team": "Brasil",
                "away_team": "Marrocos",
                "group": "C",
                "phase": "group",
                "kickoff": "2026-06-01T20:00:00+00:00",
                "home_score": 2,
                "away_score": 0,
            },
            {
                "home_team": "Marrocos",
                "away_team": "Brasil",
                "group": "C",
                "phase": "group",
                "kickoff": "2026-06-20T20:00:00+00:00",
                "home_score": 1,
                "away_score": 1,
            },
        ],
    }
    as_of = datetime(2026, 6, 10, tzinfo=UTC)
    results = load_wc_group_results(round_data, as_of=as_of, fixtures_df=pd.DataFrame())
    assert len(results) == 1
    assert results[0]["home_team"] == "Brasil"
    assert results[0]["home_score"] == 2
