"""Testes do benchmark modelo × mercado (beisebol)."""
from __future__ import annotations

from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
from models.baseball_benchmark import baseball_market_benchmark


def _snap(**kwargs) -> SuperbetEventSnapshot:
    base = dict(
        event_id=1,
        home_team="Yankees",
        away_team="Red Sox",
        event_name="Yankees·Red Sox",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=SuperbetInPlayState(
            home_score=2,
            away_score=1,
            minute=5,
            stoppage_time=None,
            home_corners=0,
            away_corners=0,
            home_yellow_cards=0,
            away_yellow_cards=0,
            ht_home_score=None,
            ht_away_score=None,
            period_label="5I",
            status="STARTED",
        ),
        h2h_odds={},
        h2h_implied={},
        totals={},
        totals_implied={},
        corners={},
        corners_implied={},
        combo_markets={},
        btts_odds={},
        next_goal_odds={},
        generosity_probs={},
        team_totals={"home": {}, "away": {}},
        first_half_totals={},
        second_half_totals={},
        yellow_cards={},
        first_half_yellow_cards={},
        team_shots={"home": {}, "away": {}},
        team_shots_on_target={"home": {}, "away": {}},
        half_markets={},
        handicap_odds={},
        handicap_implied={},
        moneyline_odds={"1": 1.80, "2": 2.10},
        moneyline_implied={"1": 0.5556, "2": 0.4762},
        spread_odds={"m1_5": {"home": 1.90, "away": 1.90}},
        spread_implied={},
        total_points_odds={"8.5": {"over": 1.91, "under": 1.91}},
        total_points_implied={},
    )
    base.update(kwargs)
    return SuperbetEventSnapshot(**base)


def test_benchmark_accepts_string_total_line_keys():
    """Chaves de total vêm como str do parser — não pode usar :g direto."""
    snap = _snap()
    out = baseball_market_benchmark(
        snap,
        model_moneyline={"1": 0.58, "2": 0.42},
        model_totals={"over_8_5": 0.52, "under_8_5": 0.48},
        model_spread={"home_m1_5": 0.51, "away_m1_5": 0.49},
    )
    assert "1" in out["moneyline"]
    assert "8.5" in out["totals"]
    assert out["totals"]["8.5"]["model_over"] == 0.52
    assert "m1_5" in out["spread"]
