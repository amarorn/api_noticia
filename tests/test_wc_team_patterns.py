"""Testes dos padrões KXL 9/10–10/10 e montagem de bilhete combo."""
from __future__ import annotations

from models.wc_team_patterns import (
    build_combo_ticket,
    get_team_patterns,
    pattern_accuracy_score,
)


def test_patterns_loaded_for_wc_teams():
    assert get_team_patterns("Brazil") is not None
    assert get_team_patterns("Brasil") is not None
    assert get_team_patterns("South Korea") is not None
    assert get_team_patterns("Coreia do Sul") is not None


def test_pattern_accuracy_south_korea_vs_czech():
    acc = pattern_accuracy_score("South Korea", "Czech Republic")
    assert acc["pattern_count"] > 0
    assert acc["score"] > 0.4
    assert acc["label"] in {"alta", "media", "baixa"}


def test_combo_ticket_korea_czech_matches_study_axes():
    ticket = build_combo_ticket("South Korea", "Czech Republic", bankroll=1000.0)
    assert ticket["available"] is True
    assert len(ticket["main_bets"]) == 2
    stats = {b["stat"] for b in ticket["main_bets"]}
    assert stats == {"goals", "yellow_cards"}
    main_labels = [b["label"] for b in ticket["main_bets"]]
    assert any("Menos de 1.5" in label for label in main_labels)
    assert any("Cartões Amarelos" in label and "Menos de 2.5" in label for label in main_labels)
    for bet in ticket["main_bets"]:
        assert bet["hit_rate"] >= 0.9
        assert "PADRÕES KXL" in bet["pattern_ref"]
    assert len(ticket["reserve_bets"]) == 2
    reserve_labels = [b["label"] for b in ticket["reserve_bets"]]
    assert any("Menos de 3.5" in label and "Gols na Partida" in label for label in reserve_labels)
    assert any("República Tcheca" in label and "Mais de 8.5" in label for label in reserve_labels)
    assert ticket["suggested_stake_pct"] > 0
    assert ticket["combined_hit_rate_estimate"] > 0


def test_combo_ticket_unknown_teams_unavailable():
    ticket = build_combo_ticket("Time X", "Time Y")
    assert ticket["available"] is False
    assert ticket["main_bets"] == []
