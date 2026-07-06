"""Testes para estratégias pareadas de blindagem."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ingest.superbet.parser import parse_superbet_event
from models.live_hedge_pair_strategies import (
    build_hedge_pair_candidates,
    build_hedge_pair_strategies,
)
from models.wc_bet_strategy import build_bet_strategy_report

FIXTURE = Path(__file__).parent / "fixtures" / "superbet_brasil_egito.json"


def _sample_inplay() -> dict:
    return {
        "current_score": "1x1",
        "prob_final_home": 0.55,
        "prob_final_draw": 0.28,
        "prob_final_away": 0.17,
        "final_line_probs": {
            "over_1_5": 0.72,
            "under_1_5": 0.28,
            "over_2_5": 0.48,
            "under_2_5": 0.52,
            "over_3_5": 0.30,
            "under_3_5": 0.70,
        },
        "btts_final": 0.62,
        "prob_next_goal_home": 0.52,
        "prob_next_goal_away": 0.35,
    }


def test_market_category_and_diversify():
    from models.wc_bet_advice import _diversify_by_category, market_category

    assert market_category("h2h") == "h2h"
    assert market_category("corners_over_9_5") == "corners"
    assert market_category("cards_over_3_5") == "cards"
    assert market_category("over_2_5") == "goals"

    class _Row:
        def __init__(self, market: str):
            self.market = market

    rows = [
        _Row("over_2_5"),
        _Row("over_1_5"),
        _Row("corners_over_9_5"),
        _Row("cards_over_4_5"),
        _Row("h2h"),
    ]
    picked = _diversify_by_category(rows, 4)
    cats = {market_category(r.market) for r in picked}
    assert "corners" in cats or "cards" in cats
    assert len(picked) == 4


def test_build_dynamic_corner_band_pairs():
    idx = {
        ("corners_over_8_5", "yes"): {
            "market": "corners_over_8_5",
            "outcome": "yes",
            "label": "Escanteios: mais de 8.5",
            "model_prob": 0.58,
            "market_odd": 1.72,
            "expected_value": 0.02,
            "edge_pp": 3.0,
            "suggested_stake_pct": 1.0,
        },
        ("corners_over_8_5", "no"): {
            "market": "corners_over_8_5",
            "outcome": "no",
            "label": "Escanteios: menos de 8.5",
            "model_prob": 0.42,
            "market_odd": 2.05,
            "expected_value": -0.05,
            "edge_pp": -2.0,
            "suggested_stake_pct": 0.5,
        },
        ("corners_over_10_5", "yes"): {
            "market": "corners_over_10_5",
            "outcome": "yes",
            "label": "Escanteios: mais de 10.5",
            "model_prob": 0.35,
            "market_odd": 2.4,
            "expected_value": -0.1,
            "edge_pp": -4.0,
            "suggested_stake_pct": 0.5,
        },
        ("corners_over_10_5", "no"): {
            "market": "corners_over_10_5",
            "outcome": "no",
            "label": "Escanteios: menos de 10.5",
            "model_prob": 0.65,
            "market_odd": 1.55,
            "expected_value": 0.01,
            "edge_pp": 2.0,
            "suggested_stake_pct": 0.8,
        },
    }
    from models.live_hedge_pair_strategies import _build_dynamic_band_pairs, build_hedge_pair_candidates

    templates = _build_dynamic_band_pairs(
        idx, prefix="corners", category="corners", name_prefix="Zona escanteios",
    )
    assert len(templates) >= 1

    inplay = {
        "current_score": "1x1",
        "final_line_probs": {"over_2_5": 0.5, "under_2_5": 0.5},
        "corner_line_probs": {"over_8_5": 0.58, "under_10_5": 0.65},
    }
    candidates = build_hedge_pair_candidates(
        market_scan=list(idx.values()),
        inplay=inplay,
        home_team="Marrocos",
        away_team="Canadá",
        minute=60,
    )
    corner_pairs = [c for c in candidates if c.get("category") == "corners"]
    assert corner_pairs, "deveria gerar par de escanteios quando odds disponíveis"


def test_select_diverse_pairs_prefers_different_categories():
    from models.live_hedge_pair_strategies import _select_diverse_pairs

    candidates = [
        {"id": "zona_2_gols", "category": "goals", "score": 100},
        {"id": "visitante_nao_perde", "category": "h2h", "score": 95},
        {"id": "corners_zona_8_5_10_5", "category": "corners", "score": 90},
        {"id": "cards_zona_3_5_4_5", "category": "cards", "score": 85},
    ]
    picked = _select_diverse_pairs(candidates, n=2)
    cats = {p["category"] for p in picked}
    assert len(cats) >= 2


def test_project_pregame_corners_and_cards():
    from models.wc_halftime_adjust import project_pregame_cards, project_pregame_corners

    corners = project_pregame_corners(lambda_home_ft=5.2, lambda_away_ft=4.1, lines=(8.5, 9.5))
    assert corners["line_probs"]["over_8_5"] > 0
    assert "under_9_5" in corners["line_probs"]

    cards = project_pregame_cards(referee_card_lambda=4.2, lines=(3.5, 4.5))
    assert cards["line_probs"]["over_3_5"] > 0


def test_build_hedge_pair_candidates_finds_complementary_pairs():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = _sample_inplay()
    from models.wc_bet_advice import scan_all_market_edges

    edges, _ = scan_all_market_edges(
        inplay,
        snap,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
    )
    candidates = build_hedge_pair_candidates(
        market_scan=edges,
        inplay=inplay,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
    )
    assert len(candidates) >= 1
    first = candidates[0]
    assert "leg_a" in first and "leg_b" in first
    assert first["coverage"]["prob_at_least_one"] >= 0.55


def test_build_hedge_pair_strategies_deterministic_without_llm():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = _sample_inplay()
    from models.wc_bet_advice import scan_all_market_edges

    edges, _ = scan_all_market_edges(
        inplay,
        snap,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
    )
    report = build_hedge_pair_strategies(
        market_scan=edges,
        inplay=inplay,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
        use_llm=False,
    )
    assert report["available"] is True
    assert len(report["strategies"]) <= 2
    assert report["strategies"][0]["titulo"]


def test_strategy_report_includes_hedge_pairs_when_not_fast():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    report = build_bet_strategy_report(
        home_team="Brasil",
        away_team="Egito",
        inplay=_sample_inplay(),
        snapshot=snap,
        benchmark=None,
        minute=17,
        bankroll=1000,
        fast=False,
    )
    hps = report.get("hedge_pair_strategies")
    assert hps is not None
    assert "strategies" in hps


def test_llm_narrate_pairs_mocked(monkeypatch):
    monkeypatch.setattr("models.live_hedge_pair_strategies.settings.openai_api_key", "sk-test")
    monkeypatch.setattr("models.live_hedge_pair_strategies.settings.live_copilot_enabled", True)

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = _sample_inplay()
    from models.wc_bet_advice import scan_all_market_edges

    edges, _ = scan_all_market_edges(
        inplay,
        snap,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
    )
    candidates = build_hedge_pair_candidates(
        market_scan=edges,
        inplay=inplay,
        home_team="Brasil",
        away_team="Egito",
        minute=17,
    )
    cid = candidates[0]["id"]
    cid2 = candidates[1]["id"] if len(candidates) > 1 else cid

    mock_response = type(
        "R",
        (),
        {
            "raise_for_status": lambda self: None,
            "json": lambda self: {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "estrategias": [
                                {
                                    "id": cid,
                                    "titulo": "Par teste A",
                                    "resumo": "Se um falhar, o outro cobre.",
                                    "stake_split": "60/40",
                                    "cenario_chave": "2 gols",
                                },
                                {
                                    "id": cid2,
                                    "titulo": "Par teste B",
                                    "resumo": "Blindagem split.",
                                    "stake_split": "50/50",
                                    "cenario_chave": "Empate",
                                },
                            ],
                        }),
                    },
                }],
            },
        },
    )()

    with patch("models.live_hedge_pair_strategies.httpx.post", return_value=mock_response):
        report = build_hedge_pair_strategies(
            market_scan=edges,
            inplay=inplay,
            home_team="Brasil",
            away_team="Egito",
            minute=17,
            use_llm=True,
        )

    assert report["available"] is True
    assert len(report["strategies"]) == 2
    assert report["strategies"][0]["llm_enriched"] is True
