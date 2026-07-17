"""Testes do sync de calendário mata-mata WC 2026."""
from __future__ import annotations

from pipelines.sync_wc_knockout_schedule import (
    _is_placeholder_team,
    _parse_sofascore_knockout_event,
    _supplement_knockout_by_known_ids,
    merge_knockout_matches,
)


def test_placeholder_team_detection():
    assert _is_placeholder_team("W102")
    assert _is_placeholder_team("L102")
    assert _is_placeholder_team("TBD")
    assert _is_placeholder_team("Winner of SF1")
    assert not _is_placeholder_team("Argentina")
    assert not _is_placeholder_team("Inglaterra")


def test_parse_sofascore_semifinal_event():
    event = {
        "id": 12812996,
        "homeTeam": {"id": 4713, "name": "England"},
        "awayTeam": {"id": 4819, "name": "Argentina"},
        "tournament": {"slug": "world-cup-knockout-stage", "name": "World Cup"},
        "roundInfo": {"name": "Semifinals"},
        "startTimestamp": 1784142000,
    }
    team_map = {
        "Inglaterra": {"sofascore_id": 4713},
        "Argentina": {"sofascore_id": 4819},
    }
    parsed = _parse_sofascore_knockout_event(event, team_map=team_map)
    assert parsed is not None
    assert parsed["phase"] == "semifinal"
    assert parsed["home_team"] == "Inglaterra"
    assert parsed["away_team"] == "Argentina"
    assert parsed["sofascore_event_id"] == 12812996
    assert parsed["schedule_source"] == "sofascore"


def test_parse_sofascore_skips_placeholder_final():
    event = {
        "id": 1,
        "homeTeam": {"id": 4698, "name": "Spain"},
        "awayTeam": {"id": 0, "name": "W102"},
        "tournament": {"slug": "world-cup-knockout-stage", "name": "World Cup"},
        "roundInfo": {"name": "Final"},
        "startTimestamp": 1784487600,
    }
    assert _parse_sofascore_knockout_event(event, team_map={}) is None


def test_merge_preserves_existing_score_and_fifa_id():
    round_data = {
        "matches": [
            {
                "id": "semifinal-franca-espanha",
                "home_team": "França",
                "away_team": "Espanha",
                "phase": "semifinal",
                "kickoff": "2026-07-14T19:00:00+00:00",
                "fifa_id_match": "400021541",
                "home_score": 0,
                "away_score": 2,
                "result_source": "fifa",
            }
        ]
    }
    incoming = [
        {
            "id": "semifinal-franca-espanha",
            "home_team": "França",
            "away_team": "Espanha",
            "phase": "semifinal",
            "kickoff": "2026-07-14T19:00:00+00:00",
            "fifa_id_match": None,
            "schedule_source": "sofascore",
            "sofascore_event_id": 99,
        }
    ]
    out, added, updated = merge_knockout_matches(round_data, incoming)
    assert added == 0
    assert updated == 1
    m = out["matches"][0]
    assert m["home_score"] == 0
    assert m["away_score"] == 2
    assert m["fifa_id_match"] == "400021541"
    assert m["sofascore_event_id"] == 99


def test_supplement_known_ids_adds_missing(monkeypatch):
    class FakeClient:
        def match_details(self, match_id: str):
            if match_id != "400021540":
                raise RuntimeError("skip")
            return {
                "IdMatch": "400021540",
                "Date": "2026-07-15T19:00:00+00:00",
                "SeasonName": [{"Description": "FIFA World Cup 2026™"}],
                "StageName": [{"Description": "Semi-final", "Locale": "en"}],
                "Home": {"TeamName": [{"Description": "England", "Locale": "en"}]},
                "Away": {"TeamName": [{"Description": "Argentina", "Locale": "en"}]},
            }

    out: list[dict] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    added = _supplement_knockout_by_known_ids(
        FakeClient(),
        seen_ids=seen_ids,
        seen_pairs=seen_pairs,
        out=out,
    )
    assert added == 1
    assert out[0]["home_team"] == "Inglaterra"
    assert out[0]["away_team"] == "Argentina"
    assert out[0]["fifa_id_match"] == "400021540"
