"""Testes do refresh de cash-out em apostas abertas."""
from __future__ import annotations

from unittest.mock import patch

from api.user_bets_store import refresh_open_bets_cashouts


def test_refresh_open_bets_cashouts_updates_eligible(tmp_path, monkeypatch):
    bets_file = tmp_path / "user_open_bets.json"
    bets_file.write_text(
        """{
  "version": 1,
  "bets": [
    {
      "id": "b1",
      "status": "open",
      "ticket_code": "ABC-12345",
      "superbet_event_id": 99,
      "event_name": "A x B",
      "home_team": "A",
      "away_team": "B",
      "picks": [{"market": "h2h", "outcome": "1"}],
      "stake": 10,
      "odds_placed": 2.0,
      "potential_return": 20,
      "cashout_value": null
    }
  ]
}""",
        encoding="utf-8",
    )
    monkeypatch.setattr("api.user_bets_store._user_bets_file", lambda: bets_file)

    with patch(
        "ingest.superbet.cashout_client.fetch_cashout_value",
        return_value={"eligible": True, "value": 12.34},
    ):
        summary = refresh_open_bets_cashouts(event_id=99)

    assert summary["updated"] == 1
    assert summary["results"][0]["cashout_value"] == 12.34
