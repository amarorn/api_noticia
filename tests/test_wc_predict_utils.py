"""Testes de cutoff temporal para palpites WC."""

from __future__ import annotations

from datetime import UTC, datetime

from pipelines.wc_predict_utils import before_date_for_match, match_is_played


def test_match_is_played():
    assert match_is_played({"home_score": 1, "away_score": 0})
    assert not match_is_played({"home_score": 1})


def test_before_date_skips_played():
    assert before_date_for_match({"home_score": 0, "away_score": 0, "kickoff": "2026-06-14T12:00:00Z"}) is None


def test_before_date_uses_kickoff_for_future():
    kick = "2026-06-20T18:00:00-04:00"
    cutoff = before_date_for_match({"kickoff": kick}, now=datetime(2026, 6, 13, tzinfo=UTC))
    assert cutoff is not None
    assert cutoff.year == 2026


def test_resolve_inplay_before_date_from_kickoff():
    from pipelines.wc_predict_utils import resolve_inplay_before_date

    now = datetime(2026, 6, 15, 20, 0, tzinfo=UTC)
    cutoff = resolve_inplay_before_date(
        "Bélgica",
        "Egito",
        kickoff_iso="2026-06-15T18:00:00-04:00",
        now=now,
    )
    assert cutoff <= now
    assert cutoff == now
