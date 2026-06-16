"""Testes de metadados e consistência de nomes no palpite WC."""
from __future__ import annotations

import pytest

from models.wc_prediction_meta import build_prediction_metadata, outcome_from_score


def test_outcome_from_score():
    assert outcome_from_score(2, 1) == "1"
    assert outcome_from_score(1, 1) == "X"
    assert outcome_from_score(0, 2) == "2"


def test_build_prediction_metadata_draw_pick():
    meta = build_prediction_metadata(
        {"1": 0.436, "X": 0.274, "2": 0.290},
        "X",
    )
    assert meta["max_prob_outcome"] == "1"
    assert meta["pick_reason"] == "empate_equilibrio"
    assert meta["uncertainty"] in {"alta", "media", "baixa"}


@pytest.mark.slow
def test_predict_team_name_aliases_consistent():
    from models.wc_artifact import load_or_train_wc_predictor

    pred, _ = load_or_train_wc_predictor(force=False)
    a = pred.predict("Canadá", "Bósnia", phase="group", season=2026)
    b = pred.predict("Canadá", "Bósnia e Herzegovina", phase="group", season=2026)
    assert a.prediction == b.prediction
    assert round(a.prob_home, 3) == round(b.prob_home, 3)
    assert round(a.prob_draw, 3) == round(b.prob_draw, 3)
    assert round(a.prob_away, 3) == round(b.prob_away, 3)
