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
