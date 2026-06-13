"""Testes de liquidação automática de apostas abertas."""
from __future__ import annotations

import json

import pytest

from models.open_bet_settle import evaluate_bet_picks, evaluate_pick, settle_open_bets_for_event


class TestEvaluatePick:
    def test_h2h_home_win(self):
        assert evaluate_pick(market="h2h", outcome="home", target_value=None, home_score=2, away_score=1)

    def test_h2h_draw(self):
        assert evaluate_pick(market="h2h", outcome="draw", target_value=None, home_score=1, away_score=1)
        assert not evaluate_pick(market="h2h", outcome="home", target_value=None, home_score=1, away_score=1)

    def test_totals_over(self):
        assert evaluate_pick(
            market="totals_2.5", outcome="over", target_value=None, home_score=2, away_score=1
        )

    def test_btts_yes(self):
        assert evaluate_pick(market="btts", outcome="yes", target_value=None, home_score=1, away_score=1)
        assert not evaluate_pick(market="btts", outcome="yes", target_value=None, home_score=1, away_score=0)

    def test_next_goal_unknown(self):
        assert evaluate_pick(market="next_goal", outcome="home", target_value=None, home_score=1, away_score=0) is None


class TestSettleOpenBets:
    def test_settle_h2h_bet(self, tmp_path, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "lake_root", tmp_path)

        open_path = tmp_path / "user_open_bets.json"
        open_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "bets": [
                        {
                            "id": "bet1",
                            "event_name": "Brasil · Argentina",
                            "home_team": "Brasil",
                            "away_team": "Argentina",
                            "picks": [{"market": "h2h", "outcome": "home"}],
                            "stake": 50.0,
                            "odds_placed": 2.0,
                            "potential_return": 100.0,
                            "status": "open",
                            "superbet_event_id": 999,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = settle_open_bets_for_event(
            event_id=999,
            home_team="Brasil",
            away_team="Argentina",
            home_score=2,
            away_score=0,
        )
        assert result.n_settled == 1
        assert result.settled_ids == ["bet1"]

        settled_path = tmp_path / "user_settled_bets.json"
        assert settled_path.exists()
        data = json.loads(settled_path.read_text(encoding="utf-8"))
        assert data["bets"][0]["result"] == "won"
        assert data["bets"][0]["profit"] == 50.0

        remaining = json.loads(open_path.read_text(encoding="utf-8"))
        assert remaining["bets"] == []

    def test_losing_bet(self, tmp_path, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "lake_root", tmp_path)

        open_path = tmp_path / "user_open_bets.json"
        picks = [
            {"market": "h2h", "outcome": "away"},
        ]
        open_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "bets": [
                        {
                            "id": "bet2",
                            "event_name": "Time A · Time B",
                            "home_team": "Time A",
                            "away_team": "Time B",
                            "picks": picks,
                            "stake": 20.0,
                            "odds_placed": 3.0,
                            "potential_return": 60.0,
                            "status": "open",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = settle_open_bets_for_event(
            event_id=1,
            home_team="Time A",
            away_team="Time B",
            home_score=1,
            away_score=0,
        )
        assert result.n_settled == 1
        settled = json.loads((tmp_path / "user_settled_bets.json").read_text(encoding="utf-8"))
        assert settled["bets"][0]["result"] == "lost"
        assert settled["bets"][0]["profit"] == -20.0


class TestCombo:
    def test_all_picks_must_win(self):
        picks = [
            {"market": "h2h", "outcome": "home"},
            {"market": "btts", "outcome": "yes"},
        ]
        assert evaluate_bet_picks(picks, 2, 1)
        assert not evaluate_bet_picks(picks, 2, 0)
