"""Testes de alertas contra o palpite do modelo."""
from __future__ import annotations

from models.wc_against_model import build_against_model_alerts, normalize_h2h_outcome


def test_normalize_h2h_outcome():
    assert normalize_h2h_outcome("away") == "2"
    assert normalize_h2h_outcome("X") == "X"


def test_build_against_model_alerts_critical():
    alerts = build_against_model_alerts(
        open_bets=[
            {
                "id": "bet-1",
                "stake": 20.0,
                "odds_placed": 2.35,
                "picks": [{"market": "h2h", "outcome": "away"}],
            }
        ],
        inplay={
            "prob_final_home": 0.15,
            "prob_final_draw": 0.55,
            "prob_final_away": 0.30,
        },
        pregame_prediction="X",
        pregame_probs={"1": 0.33, "X": 0.34, "2": 0.33},
        home_team="Canadá",
        away_team="Bósnia",
        phase="friendly",
    )
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"
    assert alerts[0]["bet_outcome"] == "2"
    assert alerts[0]["against_pregame"] is True
    assert alerts[0]["against_inplay"] is True


def test_build_against_model_alerts_none_when_aligned():
    alerts = build_against_model_alerts(
        open_bets=[
            {
                "id": "bet-1",
                "stake": 10.0,
                "odds_placed": 2.0,
                "picks": [{"market": "h2h", "outcome": "X"}],
            }
        ],
        inplay={
            "prob_final_home": 0.20,
            "prob_final_draw": 0.50,
            "prob_final_away": 0.30,
        },
        pregame_prediction="X",
        pregame_probs={"1": 0.30, "X": 0.40, "2": 0.30},
        home_team="Canadá",
        away_team="Bósnia",
        phase="friendly",
    )
    assert alerts == []
