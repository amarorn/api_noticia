"""Testes de análise dos últimos 10 jogos para bilhete combo."""
from __future__ import annotations

from models.wc_combo_last10 import _leg_hit, build_last10_analysis
from models.wc_team_patterns import build_combo_ticket


def test_leg_hit_under_goals():
    leg = {"direction": "under", "line": 1.5}
    assert _leg_hit(leg, 1.0) is True
    assert _leg_hit(leg, 2.0) is False


def test_leg_hit_under_cards():
    leg = {"direction": "under", "line": 2.5}
    assert _leg_hit(leg, 2.0) is True
    assert _leg_hit(leg, 3.0) is False


def test_build_last10_analysis_sweden_tunisia():
    ticket = build_combo_ticket("Suécia", "Tunísia", bankroll=500)
    analysis = ticket.get("last10_analysis")
    assert analysis is not None
    assert analysis["window_size"] == 10
    assert len(analysis["legs"]) == len(ticket["main_bets"])
    for leg_report in analysis["legs"]:
        assert len(leg_report["teams"]) == 2
        assert leg_report["kxl_crossing"]["hits"] is not None
        for team_block in leg_report["teams"]:
            assert len(team_block["matches"]) <= 10
            assert team_block["kxl_pattern"] is not None


def test_build_last10_analysis_without_sofascore_client():
    ticket = build_combo_ticket("Suécia", "Tunísia", bankroll=500)
    main = ticket["main_bets"]
    analysis = build_last10_analysis("Suécia", "Tunísia", main, client=None)
    assert analysis["incidents_fetched"] == 0
    assert analysis["legs"]
