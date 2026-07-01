"""Armadilhas over 1T e validador Criar Aposta."""
from __future__ import annotations

from models.inplay_bet_builder_guard import (
    assess_ht_over_trap,
    infer_market_from_label,
    scan_ht_over_traps,
    validate_bet_builder,
)


def test_ht_over_1_5_dead_at_halftime():
    trap = assess_ht_over_trap(
        "1h_over_1_5",
        "yes",
        minute=45,
        home_score=1,
        away_score=0,
        ht_home=1,
        ht_away=0,
    )
    assert trap is not None
    assert trap["severity"] == "critical"
    assert trap["code"] == "ht_over_dead"


def test_ht_over_1_5_trap_late_first_half():
    trap = assess_ht_over_trap(
        "1h_over_1_5",
        "yes",
        minute=38,
        home_score=1,
        away_score=0,
    )
    assert trap is not None
    assert trap["severity"] == "high"
    assert trap["goals_needed"] == 1


def test_ht_over_ok_early():
    trap = assess_ht_over_trap(
        "1h_over_1_5",
        "yes",
        minute=20,
        home_score=0,
        away_score=0,
    )
    assert trap is None


def test_validate_argentina_style_combo():
    legs = [
        {"market": "ft_hcap_home_m1_5", "outcome": "yes", "label": "Argentina -1.5"},
        {"market": "1h_home_over_1_5", "outcome": "yes", "label": "Mais de 1.5 Argentina 1T"},
        {"market": "1h_cs_2_0", "outcome": "yes", "label": "2:0 1T"},
        {"market": "h2h", "outcome": "1", "label": "Resultado 1"},
    ]
    result = validate_bet_builder(
        legs,
        minute=40,
        home_score=1,
        away_score=0,
        combined_odd=6.5,
    )
    assert result["valid"] is False or len(result["warnings"]) >= 1
    codes = {w.get("code") for w in result["warnings"]} | {e.get("code") for e in result["errors"]}
    assert "narrative_correlation" in codes or "ht_over_trap" in codes


def test_validate_incompatible_correct_scores():
    legs = [
        {"market": "1h_cs_2_0", "outcome": "yes"},
        {"market": "1h_cs_1_0", "outcome": "yes"},
    ]
    result = validate_bet_builder(legs, minute=30)
    assert result["valid"] is False
    assert any(e.get("code") == "legs_incompatible" for e in result["errors"])


def test_infer_market_from_superbet_label():
    inferred = infer_market_from_label("Mais de 1.5 - 1º Tempo - Total de Gols")
    assert inferred == ("1h_over_1_5", "yes")


def test_scan_ht_over_traps_on_market_scan():
    rows = [
        {"market": "1h_over_1_5", "outcome": "yes", "label": "Over 1.5 1T"},
        {"market": "h2h", "outcome": "1", "label": "Casa"},
    ]
    traps = scan_ht_over_traps(rows, minute=45, home_score=1, away_score=0)
    assert len(traps) == 1
    assert traps[0]["severity"] == "critical"


def test_contradiction_handicap_next_goal_adversario():
    """Handicap time A + Próximo gol time B = contradição."""
    legs = [
        {"market": "handicap", "outcome": "Central PE", "line": 0.5, "label": "Central PE (+0.5) Handicap"},
        {"market": "next_goal", "outcome": "Ferroviário CE", "label": "Ferroviário CE 2º Gol"},
    ]
    result = validate_bet_builder(legs, minute=45, home_score=0, away_score=1)
    codes = [w["code"] for w in result["warnings"]]
    assert "contradiction_handicap_next_goal" in codes
    assert any(w["severity"] == "critical" for w in result["warnings"] if w["code"] == "contradiction_handicap_next_goal")


def test_contradiction_handicap_over_adversario():
    """Handicap time A + Over gols time B = contradição."""
    legs = [
        {"market": "handicap", "outcome": "Central PE", "line": 0.5, "label": "Central PE (+0.5) Handicap"},
        {"market": "team_total_over", "outcome": "Ferroviário CE", "line": 1.5, "label": "Mais de 1.5 - Ferroviário CE"},
    ]
    result = validate_bet_builder(legs, minute=45, home_score=0, away_score=1)
    codes = [w["code"] for w in result["warnings"]]
    assert "contradiction_handicap_over" in codes
    assert any(w["severity"] == "critical" for w in result["warnings"] if w["code"] == "contradiction_handicap_over")


def test_correlation_next_goal_over_mesmo_time():
    """Próximo gol time + Over gols mesmo time = correlação alta."""
    legs = [
        {"market": "next_goal", "outcome": "Ferroviário CE", "label": "Ferroviário CE 2º Gol"},
        {"market": "team_total_over", "outcome": "Ferroviário CE", "line": 1.5, "label": "Mais de 1.5 - Ferroviário CE"},
    ]
    result = validate_bet_builder(legs, minute=45, home_score=0, away_score=1)
    codes = [w["code"] for w in result["warnings"]]
    assert "correlation_next_goal_over" in codes
    assert any(w["severity"] == "high" for w in result["warnings"] if w["code"] == "correlation_next_goal_over")


def test_bilhete_screenshot_completo():
    """Bilhete do screenshot: 3 pernas com 2 contradições + 1 correlação."""
    legs = [
        {"market": "next_goal", "outcome": "Ferroviário CE", "label": "Ferroviário CE 2º Gol"},
        {"market": "team_total_over", "outcome": "Ferroviário CE", "line": 1.5, "label": "Mais de 1.5 - Ferroviário CE"},
        {"market": "handicap", "outcome": "Central PE", "line": 0.5, "label": "Central PE (+0.5) Handicap"},
    ]
    result = validate_bet_builder(legs, minute=45, home_score=0, away_score=1)
    codes = [w["code"] for w in result["warnings"]]
    
    # Deve detectar TODAS as contradições/correlações
    assert "contradiction_handicap_next_goal" in codes, f"Esperado contradiction_handicap_next_goal, got {codes}"
    assert "contradiction_handicap_over" in codes, f"Esperado contradiction_handicap_over, got {codes}"
    assert "correlation_next_goal_over" in codes, f"Esperado correlation_next_goal_over, got {codes}"
    
    # 2 críticas + 1 alta
    severities = {w["code"]: w["severity"] for w in result["warnings"]}
    assert severities["contradiction_handicap_next_goal"] == "critical"
    assert severities["contradiction_handicap_over"] == "critical"
    assert severities["correlation_next_goal_over"] == "high"
