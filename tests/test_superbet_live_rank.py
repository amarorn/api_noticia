from ingest.superbet.live_rank import (
    LiveBetRank,
    is_wc_national_team,
    rank_live_event,
    rank_live_events,
)
from ingest.superbet.parser import SuperbetLiveEventSummary


def _event(**kwargs) -> SuperbetLiveEventSummary:
    base = dict(
        event_id=1,
        home_team="Brasil",
        away_team="Egito",
        event_name="Brasil·Egito",
        sport_id=75,
        tournament_id=None,
        utc_date=None,
        betradar_id=None,
        minute=25,
        home_score=1,
        away_score=1,
        period_label="1º Tempo",
        status="LIVE",
        market_count=42,
        h2h_odds={"1": 1.9, "X": 3.2, "2": 4.0},
        captured_at="2026-06-13T00:00:00Z",
    )
    base.update(kwargs)
    return SuperbetLiveEventSummary(**base)


def test_wc_national_team():
    assert is_wc_national_team("Brasil")
    assert not is_wc_national_team("Queanbeyan City")


def test_rank_national_competitive_game_top():
    rank = rank_live_event(_event())
    assert rank.tier in {"top", "good"}
    assert rank.score > 40


def test_rank_blocked_after_45_decided():
    rank = rank_live_event(
        _event(home_team="Club A", away_team="Club B", minute=81, home_score=1, away_score=3)
    )
    assert rank.tier in {"blocked", "skip", "watch"}


def test_rank_with_tick_boosts_score():
    base = rank_live_event(_event(home_team="Club A", away_team="Club B", minute=30))
    boosted = rank_live_event(
        _event(home_team="Club A", away_team="Club B", minute=30),
        tick={"top_aporte_ev": 0.12, "top_aporte_market": "over_2_5", "top_aporte_outcome": "yes"},
    )
    assert boosted.score > base.score
    assert boosted.tier == "top"


def test_latest_ticks_handles_pandas_na(tmp_path, monkeypatch):
    import pandas as pd

    from ingest.superbet import live_rank as live_rank_mod

    path = tmp_path / "live_ticks.parquet"
    df = pd.DataFrame(
        {
            "event_id": [999],
            "top_aporte_ev": [pd.NA],
            "top_aporte_market": [pd.NA],
            "top_aporte_outcome": [pd.NA],
            "prob_final_home": [0.4],
            "prob_final_draw": [0.3],
            "prob_final_away": [0.3],
            "captured_at": [pd.Timestamp("2026-06-13T05:00:00Z")],
        }
    )
    df.to_parquet(path)
    monkeypatch.setattr(live_rank_mod, "live_ticks_path", lambda: path)

    ticks = live_rank_mod._latest_ticks_by_event(max_age_minutes=9999)
    assert 999 in ticks
    assert ticks[999]["top_aporte_market"] is None
    assert ticks[999]["top_aporte_ev"] is None
    assert ticks[999]["prob_final_home"] == 0.4


def test_rank_live_events_sorted():
    events = [
        _event(event_id=1, home_team="Club A", away_team="Club B", minute=80, home_score=0, away_score=4),
        _event(event_id=2, home_team="Brasil", away_team="Egito", minute=22, home_score=0, away_score=0),
    ]
    ranked = rank_live_events(events)
    assert ranked[0][0].event_id == 2
    assert isinstance(ranked[0][1], LiveBetRank)
