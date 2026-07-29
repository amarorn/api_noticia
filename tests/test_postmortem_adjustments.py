"""Testes: detecção de placar stale e finalização ampliada."""
from __future__ import annotations

from ingest.superbet.advice import _match_is_finished
from ingest.superbet.score_stale import detect_score_stale
from models.wc_predictor import _apply_favorite_prob_cap


def test_match_finished_on_period_label():
    assert _match_is_finished(status="STARTED", period_label="END", minute=93)


def test_match_finished_when_off_live_feed_late():
    assert _match_is_finished(
        status="STARTED",
        period_label=None,
        minute=93,
        is_live_snapshot=False,
        home_score=4,
        away_score=2,
    )


def test_score_stale_scorealarm_more_goals():
    out = detect_score_stale(
        home_score=0,
        away_score=0,
        minute=50,
        scorealarm_timeline=[{"type": 4, "minute": 48, "side": 1}],
    )
    assert out["score_stale"]
    assert out["scorealarm_goals"] == 1


def test_baseball_score_stale_tick_ahead_of_snapshot():
    from ingest.superbet.score_stale import detect_baseball_score_stale

    out = detect_baseball_score_stale(
        home_score=2,
        away_score=1,
        inning=6,
        last_tick={"home_score": 4, "away_score": 2, "minute": 6},
    )
    assert out["score_stale"] is True
    assert out["tick_runs"] == 6
    assert out["snapshot_runs"] == 3


def test_favorite_cap_reduces_home_favorite():
    probs = _apply_favorite_prob_cap({"1": 0.85, "X": 0.10, "2": 0.05})
    assert probs["1"] <= 0.79
    assert probs["X"] > 0.10
