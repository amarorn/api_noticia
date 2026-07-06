"""Testes do copiloto/resumo pré-jogo."""
from __future__ import annotations

from models.pregame_llm import (
    _normalize_pregame_bilhete,
    _sanitize_pregame_copilot_payload,
    fallback_pregame_summary,
    generate_pregame_summary,
)


def _balanced_analysis() -> dict:
    return {
        "home_team": "Austrália",
        "away_team": "Egito",
        "prob_home": 0.42,
        "prob_draw": 0.16,
        "prob_away": 0.42,
        "confidence": 0.424,
        "expected_goals": "1.2x1.0",
        "poisson_score": "1x0",
        "ticket": {
            "combo": {
                "label": "Vitória Austrália + Mais de 1.5 gols",
                "model_prob": 0.27,
                "confidence": "Baixa",
            },
            "singles": [],
        },
    }


def test_fallback_summary_equilibrio():
    out = fallback_pregame_summary(_balanced_analysis())
    assert out["confianca"] == "Baixa"
    assert out["acao_sugerida"] == "aguardar"
    assert "equilibrado" in out["narrative"].lower()
    assert any("combo" in a.lower() for a in out["alertas"])


def test_fallback_summary_alerta_research():
    synthesis = {
        "favorito": "Egito",
        "confianca_geral": "Média",
        "alertas_risco": ["Lesão no atacante titular"],
    }
    out = fallback_pregame_summary(_balanced_analysis(), synthesis)
    assert out["modelo_vs_noticias"] is not None
    assert "Lesão" in out["alertas"][0] or any("Lesão" in a for a in out["alertas"])


def test_generate_summary_sem_openai(monkeypatch):
    monkeypatch.setattr("models.pregame_llm.settings.live_copilot_enabled", False)
    monkeypatch.setattr("models.pregame_llm.settings.openai_api_key", None)
    out = generate_pregame_summary(_balanced_analysis())
    assert out["enabled"] is False
    assert out["provider"] == "local"
    assert len(out["narrative"]) > 20


def test_sanitize_bilhete_llm_sem_rank_label():
    """Saída LLM incompleta não deve quebrar LiveCopilotResponse."""
    raw = {
        "tipo": "combo",
        "titulo": "Marrocos + gols",
        "pernas": [
            {"market": "2", "outcome": "Vitória Marrocos"},
            {"market": "over_1_5", "outcome": "Mais de 1.5 gols"},
        ],
    }
    bilhete = _normalize_pregame_bilhete(raw)
    assert bilhete is not None
    assert len(bilhete["pernas"]) == 2
    assert bilhete["pernas"][0]["rank"] == 1
    assert bilhete["pernas"][0]["label"] == "Vitória Marrocos"
    assert bilhete["pernas"][0]["market"] == "h2h"
    assert bilhete["pernas"][0]["outcome"] == "2"


def test_sanitize_pregame_payload_remove_internal_keys():
    payload = _sanitize_pregame_copilot_payload(
        {
            "enabled": True,
            "available": True,
            "sport": "football",
            "event_id": 0,
            "picks": [{"market": "h2h", "outcome": "1", "label": "Casa"}],
            "_analysis_fallback": {"ticket": {}},
        }
    )
    assert "_analysis_fallback" not in payload
    assert payload["picks"][0]["rank"] == 1
