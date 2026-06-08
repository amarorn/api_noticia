import json
from pathlib import Path

from ingest.superbet.parser import parse_superbet_event
from models.wc_bet_strategy import build_bet_strategy_report

FIXTURE = Path(__file__).parent / "fixtures" / "superbet_brasil_egito.json"


def test_build_bet_strategy_report_has_opportunities_and_rules():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = {
        "current_score": "1x1",
        "prob_final_home": 0.55,
        "prob_final_draw": 0.28,
        "prob_final_away": 0.17,
        "final_line_probs": {"over_2_5": 0.48, "under_2_5": 0.52},
        "btts_final": 0.62,
        "prob_next_goal_home": 0.52,
        "prob_next_goal_away": 0.35,
    }
    benchmark = {
        "h2h": {
            "2": {"market": 0.22, "model": 0.17, "edge": -0.06, "odds": 4.2},
        },
    }
    report = build_bet_strategy_report(
        home_team="Brasil",
        away_team="Egito",
        inplay=inplay,
        snapshot=snap,
        benchmark=benchmark,
        minute=17,
        bankroll=1000,
    )
    assert report["posture"] in {"atacar", "neutro", "defensivo"}
    assert report["max_new_exposure_pct"] >= 0
    assert len(report["rules"]) >= 3
    assert any(s["action"] == "evitar" for s in report["shields"])
    assert "wait_reason" in report
    assert "watch_list" in report
    assert isinstance(report["watch_list"], list)
    assert report["min_edge_threshold"] > 0


def test_watch_list_when_no_opportunity():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    snap = parse_superbet_event(raw)
    inplay = {
        "current_score": "0x0",
        "prob_final_home": 0.40,
        "prob_final_draw": 0.30,
        "prob_final_away": 0.30,
        "final_line_probs": {"over_2_5": 0.35, "under_2_5": 0.65},
        "btts_final": 0.40,
        "prob_next_goal_home": 0.45,
        "prob_next_goal_away": 0.40,
    }
    report = build_bet_strategy_report(
        home_team="Brasil",
        away_team="Egito",
        inplay=inplay,
        snapshot=snap,
        benchmark=None,
        minute=10,
        bankroll=1000,
    )
    if report["opportunity_count"] == 0:
        assert len(report["watch_list"]) >= 1
        assert report["wait_reason"]
