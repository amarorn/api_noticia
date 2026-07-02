"""Testes do bilhete sugerido pelo copiloto."""
from __future__ import annotations

from models.live_copilot_bilhete import (
    fallback_bilhete_from_optimizer,
    football_bilhete_candidates,
    validate_copilot_bilhete,
)


def test_football_bilhete_candidates_dedup_scan():
    advice = {
        "strategy": {
            "opportunities": [
                {
                    "market": "ft_over_2_5",
                    "outcome": "yes",
                    "label": "Over 2.5",
                    "market_odd": 1.9,
                    "expected_value": 0.12,
                }
            ],
            "market_scan": [
                {
                    "market": "ft_over_2_5",
                    "outcome": "yes",
                    "label": "Over 2.5",
                    "market_odd": 1.9,
                    "expected_value": 0.12,
                },
                {
                    "market": "btts",
                    "outcome": "yes",
                    "label": "Ambas marcam",
                    "market_odd": 1.75,
                    "expected_value": 0.08,
                },
            ],
        }
    }
    candidates = football_bilhete_candidates(advice)
    keys = {f"{c['market']}:{c['outcome']}" for c in candidates}
    assert "ft_over_2_5:yes" in keys
    assert "btts:yes" in keys
    assert len(candidates) == 2


def test_validate_copilot_bilhete_rejects_unknown_leg():
    advice = {
        "superbet_event_id": 1,
        "minute": 60,
        "current_score": "1x0",
        "inplay_summary": {},
    }
    candidates = [
        {
            "market": "ft_over_2_5",
            "outcome": "yes",
            "label": "Over 2.5",
            "market_odd": 1.9,
            "model_prob": 0.6,
            "expected_value": 0.1,
        }
    ]
    parsed = {
        "bilhete": {
            "tipo": "combo",
            "titulo": "Teste",
            "resumo": "Combo",
            "pernas": [
                {
                    "rank": 1,
                    "market": "ft_over_2_5",
                    "outcome": "yes",
                    "label": "Over 2.5",
                    "papel": "ancora",
                },
                {
                    "rank": 2,
                    "market": "h2h",
                    "outcome": "1",
                    "label": "Inventado",
                    "papel": "complemento",
                },
            ],
        }
    }
    bilhete = validate_copilot_bilhete(parsed, candidates=candidates, advice=advice, sport="football")
    assert bilhete is not None
    assert len(bilhete["pernas"]) == 1


def test_fallback_bilhete_from_optimizer():
    advice = {
        "superbet_event_id": 9,
        "minute": 70,
        "current_score": "2x1",
        "inplay_summary": {},
        "optimized_tickets": {
            "ft": [
                {
                    "valid": True,
                    "score": 0.85,
                    "combined_odd": 3.2,
                    "combined_ev": 0.15,
                    "period_mix": "ft",
                    "legs": [
                        {
                            "market": "ft_over_2_5",
                            "outcome": "yes",
                            "label": "Over 2.5",
                            "market_odd": 1.8,
                            "model_prob": 0.62,
                            "expected_value": 0.11,
                            "edge_pp": 8.0,
                        },
                        {
                            "market": "btts",
                            "outcome": "yes",
                            "label": "BTTS",
                            "market_odd": 1.7,
                            "model_prob": 0.58,
                            "expected_value": 0.06,
                            "edge_pp": 4.0,
                        },
                    ],
                }
            ]
        },
    }
    bilhete = fallback_bilhete_from_optimizer(advice, sport="football")
    assert bilhete is not None
    assert bilhete["tipo"] == "combo"
    assert len(bilhete["pernas"]) == 2
    assert bilhete["combined_odd"] is not None
