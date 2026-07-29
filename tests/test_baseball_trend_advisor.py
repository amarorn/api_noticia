"""Testes trend advisor + cash-out beisebol."""
from __future__ import annotations

import json

import pytest

from models.baseball_cashout import advise_baseball_cashout, cashout_to_dict
from models.baseball_trend_advisor import (
    build_baseball_trend_report,
    load_baseball_event_ticks,
    parse_baseball_tick,
)
from models.wc_bet_advice import UserBetInput, apply_trend_to_cashout


def _tick_raw(
    *,
    inning: int,
    home: int,
    away: int,
    ml_home: float = 0.45,
    ml_away: float = 0.55,
) -> dict:
    return {
        "event_id": 12_345_678,
        "home_team": "Team A",
        "away_team": "Team B",
        "captured_at": f"2026-07-19T0{inning}:00:00Z",
        "raw_market_count": 12,
        "moneyline_implied": {"1": ml_home, "2": ml_away},
        "total_points_implied": {"8.5": {"over": 0.52, "under": 0.48}},
        "inplay": {
            "home_score": home,
            "away_score": away,
            "minute": inning,
            "status": "LIVE",
        },
    }


def test_parse_baseball_tick_scales_inning_to_minute():
    tick = parse_baseball_tick(_tick_raw(inning=7, home=3, away=1))
    assert tick.minute == 70
    assert tick.total_goals == 4
    assert tick.h2h_implied["1"] == 0.45


def test_load_baseball_event_ticks_from_bronze(tmp_path):
    event_dir = tmp_path / "12345678"
    event_dir.mkdir()
    (event_dir / "20260719T010000Z.json").write_text(
        json.dumps(_tick_raw(inning=3, home=1, away=0)), encoding="utf-8"
    )
    (event_dir / "20260719T020000Z.json").write_text(
        json.dumps(_tick_raw(inning=5, home=2, away=0)), encoding="utf-8"
    )
    ticks = load_baseball_event_ticks(event_dir)
    assert len(ticks) == 2
    assert ticks[-1].home_score == 2


def test_apply_trend_to_baseball_cashout(monkeypatch):
    monkeypatch.setattr("config.settings.live_cashout_use_trend", True)
    bet = UserBetInput(market="moneyline", outcome="2", stake=50.0, odds_placed=2.0)
    inplay = {"moneyline_probs": {"1": 0.46, "2": 0.54}, "prob_away_win": 0.54}
    base = advise_baseball_cashout(bet, inplay, inning=4)
    assert base.action == "manter"
    trend = {
        "position_advice": {
            "action": "exit",
            "urgency": "high",
            "confidence": 0.88,
            "reasoning": "Mercado colapsando contra a aposta",
        }
    }
    merged = apply_trend_to_cashout(base, trend)
    assert merged.action in {"cashout_parcial", "cashout"}
    assert merged.trend_influenced is True
    payload = cashout_to_dict(merged)
    assert payload["trend_influenced"] is True


def test_build_baseball_trend_report_requires_two_ticks(tmp_path, monkeypatch):
    monkeypatch.setattr("config.settings.lake_root", tmp_path)
    event_id = 12_345_678
    event_dir = tmp_path / "bronze" / "superbet" / "events" / str(event_id)
    event_dir.mkdir(parents=True)
    (event_dir / "20260719T010000Z.json").write_text(
        json.dumps(_tick_raw(inning=3, home=0, away=0)), encoding="utf-8"
    )
    report = build_baseball_trend_report(
        event_id=event_id,
        home_team="Team A",
        away_team="Team B",
        user_bet={"market": "moneyline", "outcome": "2", "picks": []},
        event_snapshot_raw=_tick_raw(inning=3, home=0, away=0),
    )
    assert report is None

    (event_dir / "20260719T020000Z.json").write_text(
        json.dumps(_tick_raw(inning=5, home=3, away=0, ml_home=0.75, ml_away=0.25)),
        encoding="utf-8",
    )
    report = build_baseball_trend_report(
        event_id=event_id,
        home_team="Team A",
        away_team="Team B",
        user_bet={
            "market": "moneyline",
            "outcome": "2",
            "picks": [{"market": "moneyline", "outcome": "2"}],
        },
        event_snapshot_raw=_tick_raw(inning=5, home=3, away=0),
    )
    assert report is not None
    assert report.get("position_advice") is not None
    trend_text = (report.get("dominant_trend") or "").lower()
    assert "gol" not in trend_text
    assert "corrida" in trend_text
