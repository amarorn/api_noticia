"""Testes de mercados por período (F5 / entrada) no beisebol."""
from __future__ import annotations

from ingest.superbet.baseball_period_markets import extract_baseball_period_markets
from ingest.superbet.parser import parse_superbet_event
from models.baseball_bet_advice import build_baseball_bet_advice_report
from models.baseball_inplay import simulate_baseball_inplay


def _period_markets_payload() -> list[dict]:
    return [
        {
            "name": "Entradas 1 a 5 - Total",
            "odds": [
                {"price": 1.85, "status": 1, "metadata": {"code": "+", "name": "Mais", "special_bet_value": "4.5"}},
                {"price": 1.95, "status": 1, "metadata": {"code": "-", "name": "Menos", "special_bet_value": "4.5"}},
            ],
        },
        {
            "name": "Entradas 1 a 5 - 1x2",
            "odds": [
                {"price": 2.10, "status": 1, "metadata": {"code": "1", "name": "Hanwha Eagles"}},
                {"price": 1.70, "status": 1, "metadata": {"code": "2", "name": "Kiwoom Heroes"}},
            ],
        },
        {
            "name": "Entradas 1 a 5 - handicap",
            "odds": [
                {
                    "price": 1.90,
                    "status": 1,
                    "metadata": {"code": "1", "name": "Hanwha Eagles", "special_bet_value": "+1.5"},
                },
                {
                    "price": 1.90,
                    "status": 1,
                    "metadata": {"code": "2", "name": "Kiwoom Heroes", "special_bet_value": "-1.5"},
                },
            ],
        },
        {
            "name": "Entrada 3 - Total de Corridas",
            "odds": [
                {"price": 1.80, "status": 1, "metadata": {"code": "+", "name": "Mais", "special_bet_value": "1.5"}},
                {"price": 2.00, "status": 1, "metadata": {"code": "-", "name": "Menos", "special_bet_value": "1.5"}},
            ],
        },
        {
            "name": "Entrada 3 - 1X2",
            "odds": [
                {"price": 3.20, "status": 1, "metadata": {"code": "1", "name": "Hanwha Eagles"}},
                {"price": 2.50, "status": 1, "metadata": {"code": "2", "name": "Kiwoom Heroes"}},
                {"price": 2.80, "status": 1, "metadata": {"code": "X", "name": "Empate"}},
            ],
        },
        {
            "name": "Entrada Com a Maior Pontuação",
            "odds": [
                {"price": 5.0, "status": 1, "metadata": {"name": "Entrada 1"}},
                {"price": 4.5, "status": 1, "metadata": {"name": "Entrada 3"}},
            ],
        },
        {
            "name": "Corrida 7 (incl. entradas extras)",
            "odds": [
                {"price": 1.75, "status": 1, "metadata": {"code": "YES", "name": "Sim"}},
                {"price": 2.05, "status": 1, "metadata": {"code": "NO", "name": "Não"}},
            ],
        },
    ]


def test_extract_baseball_period_markets():
    markets = _period_markets_payload()
    parsed = extract_baseball_period_markets(markets, "Hanwha Eagles", "Kiwoom Heroes")
    assert parsed["f5"]["total"]["4.5"]["over"] == 1.85
    assert parsed["f5"]["moneyline"]["1"] == 2.10
    assert parsed["f5"]["spread"]["p1_5"]["home"] == 1.90
    assert parsed["innings"]["3"]["total"]["1.5"]["over"] == 1.80
    assert parsed["innings"]["3"]["1x2"]["X"] == 2.80
    assert parsed["highest_inning"]["3"] == 4.5
    assert parsed["run_n"]["7"]["yes"] == 1.75
    assert parsed["display_names"]["f5_total"] == "Entradas 1 a 5 - Total"


def test_parse_superbet_event_includes_period_markets():
    ev = {
        "event_id": 99,
        "fixture": {
            "event_id": 99,
            "event_name": "Hanwha Eagles·Kiwoom Heroes",
            "sport_id": 20,
            "event_tags": "superLive",
        },
        "inplay_stats": {
            "home_team_score": "1",
            "away_team_score": "2",
            "periods": [{"num": 1, "home_team_score": "1", "away_team_score": "2", "type": 1}],
        },
        "inplay_stats_metadata": {"event_status_label": "2I", "status": "STARTED"},
        "markets": _period_markets_payload(),
    }
    snap = parse_superbet_event(ev)
    assert snap.baseball_period_markets["f5"]["total"]
    assert snap.baseball_market_names["f5_total"] == "Entradas 1 a 5 - Total"


def test_simulate_period_probs():
    period_markets = extract_baseball_period_markets(
        _period_markets_payload(), "Hanwha Eagles", "Kiwoom Heroes"
    )
    inplay = simulate_baseball_inplay(
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        home_score=1,
        away_score=2,
        inning=2,
        moneyline_odds={"1": 2.0, "2": 1.8},
        period_markets=period_markets,
        innings_observed=[{"num": 1, "home": 1, "away": 2}],
        n_simulations=3000,
        random_seed=42,
    )
    assert "f5_over_4_5" in inplay.period_probs
    assert "inning_3_over_1_5" in inplay.period_probs
    assert "highest_inning_3" in inplay.period_probs
    assert "run_7_yes" in inplay.period_probs


def test_period_aportes_use_superbet_market_names():
    from tests.test_baseball_bet_advice import _make_snapshot

    period_markets = extract_baseball_period_markets(
        _period_markets_payload(), "Hanwha Eagles", "Kiwoom Heroes"
    )
    inplay = simulate_baseball_inplay(
        home_team="Hanwha Eagles",
        away_team="Kiwoom Heroes",
        home_score=0,
        away_score=3,
        inning=3,
        moneyline_odds={"1": 3.0, "2": 1.4},
        period_markets=period_markets,
        innings_observed=[
            {"num": 1, "home": 0, "away": 1},
            {"num": 2, "home": 0, "away": 2},
        ],
        n_simulations=4000,
        random_seed=7,
    )
    snapshot = _make_snapshot(
        baseball_period_markets=period_markets,
        baseball_market_names=period_markets["display_names"],
    )
    report = build_baseball_bet_advice_report(inplay=inplay, snapshot=snapshot, bankroll=1000)
    period_aportes = [a for a in report["aportes"] if a["market"].startswith(("f5_", "inning_", "highest_", "run_"))]
    if period_aportes:
        assert all(a["market_display"] for a in period_aportes)
        assert any("Entradas 1 a 5" in a["market_display"] or "Entrada" in a["market_display"] for a in period_aportes)
