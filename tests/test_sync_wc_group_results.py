"""Testes do CLI sync-wc-group-results."""
from __future__ import annotations

import json

import pytest

from pipelines.sync_wc_group_results import (
    ResultUpdate,
    apply_updates,
    extract_fifa_results,
    parse_results_csv,
    sync_wc_group_results,
    _schedule_index,
)


@pytest.fixture
def round_data():
    return {
        "season": 2026,
        "phase": "group",
        "matches": [
            {
                "id": "A-r1",
                "home_team": "México",
                "away_team": "África do Sul",
                "group": "A",
                "phase": "group",
                "kickoff": "2026-06-11T20:00:00+00:00",
            },
            {
                "id": "B-r1",
                "home_team": "Canadá",
                "away_team": "Bósnia",
                "group": "B",
                "phase": "group",
            },
        ],
    }


def test_parse_results_csv(round_data):
    csv_text = "mandante,visitante,gols_casa,gols_fora\nMéxico,África do Sul,2,1\n"
    updates, skipped = parse_results_csv(
        csv_text,
        schedule_index=_schedule_index(round_data),
    )
    assert len(updates) == 1
    assert updates[0].home_score == 2
    assert updates[0].away_score == 1
    assert not skipped


def test_parse_csv_reversed_teams(round_data):
    csv_text = "mandante,visitante,placar\nÁfrica do Sul,México,1-2\n"
    updates, _ = parse_results_csv(csv_text, schedule_index=_schedule_index(round_data))
    assert updates[0].home_team == "México"
    assert updates[0].home_score == 2


def test_extract_fifa_results(round_data):
    fifa_raw = [
        {
            "Period": 10,
            "MatchStatus": 10,
            "HomeTeam": {"TeamName": [{"Locale": "en-GB", "Description": "Mexico"}]},
            "AwayTeam": {"TeamName": [{"Locale": "en-GB", "Description": "South Africa"}]},
            "HomeTeamScore": 2,
            "AwayTeamScore": 0,
        }
    ]
    updates, _ = extract_fifa_results(round_data, fifa_raw)
    assert len(updates) == 1
    assert updates[0].home_team == "México"
    assert updates[0].home_score == 2


def test_apply_and_sync(tmp_path, round_data):
    round_file = tmp_path / "wc_2026.json"
    round_file.write_text(json.dumps(round_data, ensure_ascii=False), encoding="utf-8")
    csv_file = tmp_path / "results.csv"
    csv_file.write_text(
        "mandante,visitante,gols_casa,gols_fora\nCanadá,Bósnia,3,0\n",
        encoding="utf-8",
    )

    report = sync_wc_group_results(
        round_file=round_file,
        source="csv",
        csv_path=csv_file,
        backup=False,
    )
    assert len(report.updated) == 1
    saved = json.loads(round_file.read_text(encoding="utf-8"))
    canada = next(m for m in saved["matches"] if m["id"] == "B-r1")
    assert canada["home_score"] == 3
    assert canada["away_score"] == 0
    assert canada["result_source"] == "csv"


def test_sync_dry_run_no_write(tmp_path, round_data):
    round_file = tmp_path / "wc.json"
    original = json.dumps(round_data)
    round_file.write_text(original, encoding="utf-8")
    csv_file = tmp_path / "r.csv"
    csv_file.write_text("mandante,visitante,gols_casa,gols_fora\nMéxico,África do Sul,1,0\n")

    sync_wc_group_results(
        round_file=round_file,
        source="csv",
        csv_path=csv_file,
        dry_run=True,
    )
    assert round_file.read_text(encoding="utf-8") == original


def test_apply_updates_idempotent(round_data):
    upd = [
        ResultUpdate(
            home_team="México",
            away_team="África do Sul",
            home_score=2,
            away_score=1,
            source="csv",
        )
    ]
    data, _ = apply_updates(round_data, upd)
    _, unchanged = apply_updates(data, upd)
    assert unchanged == 1


def test_schedule_index_includes_knockout():
    data = {
        "matches": [
            {
                "id": "semi",
                "home_team": "França",
                "away_team": "Espanha",
                "phase": "semifinal",
            },
            {
                "id": "rep",
                "home_team": "A",
                "away_team": "B",
                "phase": "repescagem",
            },
        ]
    }
    idx = _schedule_index(data)
    assert ("França", "Espanha") in idx
    assert ("A", "B") not in idx


def test_apply_updates_knockout_score():
    data = {
        "matches": [
            {
                "id": "semifinal-franca-espanha",
                "home_team": "França",
                "away_team": "Espanha",
                "phase": "semifinal",
            }
        ]
    }
    updates = [
        ResultUpdate(
            home_team="França",
            away_team="Espanha",
            home_score=0,
            away_score=2,
            source="fifa",
        )
    ]
    out, unchanged = apply_updates(data, updates)
    assert unchanged == 0
    assert out["matches"][0]["home_score"] == 0
    assert out["matches"][0]["away_score"] == 2
