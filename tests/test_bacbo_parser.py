"""Testes do parser Bac Bo Evolution."""
from __future__ import annotations

from ingest.superbet.bacbo_parser import (
    extract_instance_from_ws_url,
    extract_table_id_from_ws_url,
    normalize_bacbo_winner,
    parse_bacbo_ws_batch,
    parse_bacbo_ws_payload,
)
from ingest.superbet.bacbo_store import append_bacbo_rounds, list_bacbo_rounds


def test_normalize_bacbo_winner():
    assert normalize_bacbo_winner("Player") == "player"
    assert normalize_bacbo_winner("Banker") == "banker"
    assert normalize_bacbo_winner("Tie") == "tie"


def test_extract_table_id_from_ws_url():
    url = (
        "wss://superbetbr.evo-games.com/public/bacbo/player/game/"
        "SuperbetBacBo001/socket?messageFormat=json"
    )
    assert extract_table_id_from_ws_url(url) == "SuperbetBacBo001"


def test_parse_game_resolved():
    raw = """
    {
      "id": "1",
      "type": "bacbo.gameResolved",
      "args": {
        "gameId": "round-99",
        "winner": "Player",
        "playerScore": 8,
        "bankerScore": 5
      }
    }
    """
    rounds = parse_bacbo_ws_payload(raw, table_id="SuperbetBacBo001")
    assert len(rounds) == 1
    assert rounds[0].round_id == "round-99"
    assert rounds[0].winner == "player"
    assert rounds[0].player_score == 8
    assert rounds[0].banker_score == 5


def test_parse_history_batch():
    raw = """
    {
      "type": "bacbo.pastResults",
      "args": {
        "results": [
          {"gameId": "a1", "result": "Banker", "playerScore": 3, "bankerScore": 7},
          {"gameId": "a2", "result": "Tie", "playerScore": 6, "bankerScore": 6}
        ]
      }
    }
    """
    rounds = parse_bacbo_ws_payload(raw, table_id="T1")
    assert len(rounds) == 2
    assert {r.winner for r in rounds} == {"banker", "tie"}


def test_parse_bacbo_ws_batch_dedupes():
    msg = '{"type":"bacbo.gameResolved","args":{"gameId":"x1","winner":"Player"}}'
    rounds = parse_bacbo_ws_batch([msg, msg], table_id="T1")
    assert len(rounds) == 1


def test_winning_spots_and_dice():
    raw = """
    {
      "type": "bacbo.gameResolved",
      "args": {
        "gameId": "g2",
        "winningSpots": ["Banker"],
        "playerDice": [3, 4],
        "bankerDice": [5, 5]
      }
    }
    """
    rounds = parse_bacbo_ws_payload(raw, table_id="SuperbetBacBo001")
    assert len(rounds) == 1
    assert rounds[0].winner == "banker"
    assert rounds[0].player_score == 7
    assert rounds[0].banker_score == 10


def test_extract_instance_from_ws_url():
    url = (
        "wss://superbetbr.evo-games.com/public/bacbo/player/game/SuperbetBacBo001/socket"
        "?instance=09n1b2-t4z4rkx3vuctbja6-SuperbetBacBo001"
    )
    assert extract_instance_from_ws_url(url) == "09n1b2-t4z4rkx3vuctbja6-SuperbetBacBo001"


def test_bacbo_store_append_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    raw = '{"type":"bacbo.gameResolved","args":{"gameId":"s1","winner":"Banker","playerScore":2,"bankerScore":9}}'
    records = parse_bacbo_ws_payload(raw, table_id="SuperbetBacBo001")
    result = append_bacbo_rounds(records, raw_messages=[raw], ws_url="wss://test/socket")
    assert result["inserted"] == 1

    listed = list_bacbo_rounds(table_id="SuperbetBacBo001", limit=10)
    assert listed["count"] == 1
    assert listed["rounds"][0]["winner"] == "banker"
    assert listed["stats"]["banker"] == 1

    again = append_bacbo_rounds(records)
    assert again["inserted"] == 0


def test_casino_bacbo_ingest_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app

    monkeypatch.setattr("config.settings.api_key", None)
    monkeypatch.setattr("config.settings.lake_root", tmp_path)

    client = TestClient(app)
    payload = {
        "table_id": "SuperbetBacBo001",
        "messages": [
            '{"type":"bacbo.gameResolved","args":{"gameId":"api-1","winner":"Player","playerScore":4,"bankerScore":2}}'
        ],
    }
    resp = client.post("/casino/bacbo/ingest", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 1
    assert body["parsed"] == 1

    listed = client.get("/casino/bacbo/rounds?table_id=SuperbetBacBo001&limit=5")
    assert listed.status_code == 200
    assert listed.json()["count"] >= 1
