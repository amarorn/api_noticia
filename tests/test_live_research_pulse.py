"""Testes para Live Research Pulse — deep research ao vivo."""
from __future__ import annotations

import pytest

from ingest.research.live_research_pulse import (
    LiveResearchError,
    apply_live_research_to_lambda,
    _build_live_query,
    _get_cached,
    _set_cached,
)


def test_build_live_query_basic():
    query = _build_live_query("Brasil", "Argentina", 45, 1, 0)
    assert "Brasil" in query
    assert "Argentina" in query
    assert "minuto 45" in query
    assert "placar 1-0" in query


def test_build_live_query_with_events():
    events = [
        {"type": "goal", "minute": 23},
        {"type": "red_card", "minute": 38},
    ]
    query = _build_live_query("Brasil", "Argentina", 45, 1, 0, events)
    assert "goal min 23" in query
    assert "red_card min 38" in query


def test_apply_live_research_lesao_home():
    """Lesão no home: ataque home -15% (home marca menos), defesa home -5% (away marca mais)."""
    research = {
        "eventos_detectados": [
            {
                "tipo": "lesao",
                "time_afetado": "home",
                "impacto_estimado": {
                    "ataque_pct": -15,
                    "defesa_pct": -5,
                    "gols_esperados_delta": -0.3,
                },
            }
        ]
    }
    lam_h, lam_a, alerts = apply_live_research_to_lambda(1.5, 1.2, research)
    # home ataque -15% -> home λ reduz (1.5 * 0.85 = 1.275) + delta -0.3 = 0.975
    assert lam_h == pytest.approx(0.975, abs=0.01)
    # home defesa -5% -> away λ aumenta (1.2 * 1.05 = 1.26)
    assert lam_a == pytest.approx(1.26, abs=0.01)
    assert any("lesao home: ataque -15%" in a for a in alerts)
    assert any("lesao home defesa: away λ -5%" in a for a in alerts)


def test_apply_live_research_cartao_vermelho():
    """Cartão vermelho no away: ataque away -20% (away marca menos), defesa away +15% (home marca menos)."""
    research = {
        "eventos_detectados": [
            {
                "tipo": "cartao_vermelho",
                "time_afetado": "away",
                "impacto_estimado": {
                    "ataque_pct": -20,
                    "defesa_pct": 15,
                    "gols_esperados_delta": 0.0,
                },
            }
        ]
    }
    lam_h, lam_a, alerts = apply_live_research_to_lambda(1.5, 1.2, research)
    # away ataque -20% -> away λ reduz (1.2 * 0.8 = 0.96)
    assert lam_a == pytest.approx(0.96, abs=0.01)
    # away defesa +15% -> home λ reduz (1.5 * 0.85 = 1.275)
    assert lam_h == pytest.approx(1.275, abs=0.01)
    assert any("cartao_vermelho away: ataque -20%" in a for a in alerts)
    assert any("cartao_vermelho away defesa: home λ +15%" in a for a in alerts)


def test_apply_live_research_substituicao_ofensiva():
    research = {
        "eventos_detectados": [
            {
                "tipo": "substituicao",
                "time_afetado": "home",
                "impacto_estimado": {
                    "ataque_pct": 10,
                    "defesa_pct": 0,
                    "gols_esperados_delta": 0.2,
                },
            }
        ]
    }
    lam_h, lam_a, alerts = apply_live_research_to_lambda(1.5, 1.2, research)
    assert lam_h > 1.5  # aumentou
    assert lam_a == 1.2  # não mudou


def test_apply_live_research_empty():
    lam_h, lam_a, alerts = apply_live_research_to_lambda(1.5, 1.2, {})
    assert lam_h == 1.5
    assert lam_a == 1.2
    assert alerts == []


def test_apply_live_research_clamp():
    """Garante que λ não sai dos limites [0.05, 5.0]."""
    research = {
        "eventos_detectados": [
            {
                "tipo": "lesao",
                "time_afetado": "home",
                "impacto_estimado": {
                    "ataque_pct": -90,
                    "gols_esperados_delta": -5.0,
                },
            }
        ]
    }
    lam_h, lam_a, alerts = apply_live_research_to_lambda(1.5, 1.2, research)
    assert lam_h >= 0.05
    assert lam_h <= 5.0


def test_cache_get_set():
    _set_cached("test_event", {"foo": "bar"})
    assert _get_cached("test_event") == {"foo": "bar"}
    # Cache miss para evento inexistente
    assert _get_cached("nonexistent") is None
