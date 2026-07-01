"""Testes do gate de prontidão do ensemble in-play."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from pipelines.inplay_ensemble_readiness import assess_ensemble_readiness


@pytest.fixture
def mock_reconcile(monkeypatch, tmp_path):
    df = pd.DataFrame(
        {
            "match_confidence": [0.9, 0.8, 0.5, 0.75],
            "bet_id": ["a", "b", "c", "d"],
        }
    )

    def _load(_user: str):
        return df

    monkeypatch.setattr(
        "pipelines.user_bet_reconciliation.load_reconciliation",
        _load,
    )
    monkeypatch.setattr(
        "pipelines.inplay_synthetic_feedback.count_synthetic_examples",
        lambda: 120,
    )
    monkeypatch.setattr(
        "pipelines.inplay_ensemble_readiness._inplay_delta_from_benchmark",
        lambda: -0.02,
    )

    art = tmp_path / "artifacts"
    art.mkdir()
    (art / "inplay_gbm_feedback_vtest.json").write_text(
        json.dumps({"brier_delta": 0.001}),
        encoding="utf-8",
    )
    monkeypatch.setattr("config.settings.lake_root", tmp_path)


def test_assess_shadow_mode(monkeypatch, mock_reconcile):
    monkeypatch.setattr(
        "config.settings.inplay_ensemble_shadow_mode",
        True,
    )
    monkeypatch.setattr(
        "config.settings.inplay_ensemble_min_feedback_hi",
        150,
    )
    monkeypatch.setattr(
        "config.settings.inplay_ensemble_prod_feedback_hi",
        500,
    )
    monkeypatch.setattr(
        "config.settings.inplay_ensemble_min_tick_examples",
        150,
    )

    report = assess_ensemble_readiness("test")
    assert report.mode == "shadow"
    assert report.ready_for_production is False
    assert report.n_feedback_high_confidence == 3
    assert report.n_tick_examples == 120
    assert report.inplay_delta_brier == pytest.approx(-0.02)


def test_ensemble_shadow_summary():
    from models.wc_inplay import InPlayResult, _ensemble_shadow_summary

    base = dict(
        home_team="A",
        away_team="B",
        home_score=1,
        away_score=0,
        minute=45,
        match_minutes=90,
        remaining_fraction=0.5,
        lambda_full_home=1.2,
        lambda_full_away=0.9,
        lambda_remaining_home=0.6,
        lambda_remaining_away=0.45,
        rho_used=0.0,
        prob_final_home=0.5,
        prob_final_draw=0.3,
        prob_final_away=0.2,
        prob_ht_home=0.4,
        prob_ht_draw=0.35,
        prob_ht_away=0.25,
        prob_sh_home=0.45,
        prob_sh_draw=0.32,
        prob_sh_away=0.23,
        prob_no_more_goals=0.1,
        prob_next_goal_home=0.55,
        prob_next_goal_away=0.35,
        final_line_probs={},
        remainder_line_probs={},
        ht_line_probs={},
        second_half_line_probs={},
        team_final_line_probs={},
        top_final_scores={},
        ht_correct_scores={},
        sh_correct_scores={},
        ht_exact_totals={},
        sh_exact_totals={},
        ht_home_exact={},
        ht_away_exact={},
        sh_home_exact={},
        sh_away_exact={},
        ht_handicap_probs={},
        sh_handicap_probs={},
        top_ht_ft={},
        combo_markets={},
        btts_final=0.5,
        n_simulations=1000,
        handicap_probs={},
    )
    poisson = InPlayResult(**base)
    ensemble = InPlayResult(**{**base, "prob_final_home": 0.55, "prob_final_draw": 0.25, "prob_final_away": 0.2})
    summary = _ensemble_shadow_summary(poisson, ensemble)
    assert summary["prob_l1_delta"] == pytest.approx(0.1)
