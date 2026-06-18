"""Testes de recalibração 2T com stats congeladas do 1T."""
from __future__ import annotations

from unittest.mock import patch

from config import settings
from ingest.superbet.halftime_snapshot import (
    HalftimeFrozenStats,
    _load_from_ticks,
    load_halftime_stats,
    load_or_freeze_halftime,
    save_halftime_stats,
)
from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState
from models.wc_bet_advice import _aporte_candidates
from models.wc_halftime_adjust import (
    adjust_second_half_goal_lambdas,
    build_halftime_report,
    project_halftime_corners,
    project_live_corners,
)
from models.wc_inplay import simulate_inplay


def _harju_stats() -> HalftimeFrozenStats:
    """Fixture evento 13368253 — HT 0×0, esc 3×4, amarelos 2×0."""
    return HalftimeFrozenStats(
        event_id=13368253,
        ht_home_score=0,
        ht_away_score=0,
        home_corners_1h=3,
        away_corners_1h=4,
        home_yellows_1h=2,
        away_yellows_1h=0,
        frozen_at="2026-06-11T01:00:00Z",
        home_team="Harju Laagri",
        away_team="Kuressaare",
    )


def test_goal_adjust_boosts_home_with_corner_pressure_no_goals():
    stats = _harju_stats()
    adj = adjust_second_half_goal_lambdas(
        lambda_full_home=1.2,
        lambda_full_away=1.0,
        stats=stats,
    )
    assert adj.home_2h_factor >= 1.0
    assert any("escanteios" in r.lower() or "amarelos" in r.lower() for r in adj.reasons)


def test_project_halftime_corners_ft_above_observed():
    stats = _harju_stats()
    proj = project_halftime_corners(stats, lambda_home_ft=5.0, lambda_away_ft=5.0)
    assert proj["expected_ft_total"] > stats.home_corners_1h + stats.away_corners_1h
    assert proj["expected_ft_total"] > 7.0


def test_project_live_corners_mid_match():
    proj = project_live_corners(
        home_corners=2,
        away_corners=1,
        minute=38,
        lambda_home_ft=5.5,
        lambda_away_ft=4.2,
        lines=(7.5, 8.5, 9.5),
    )
    assert proj["observed_total"] == 3
    assert proj["expected_ft_total"] > 3.0
    assert proj["prob_home_more_corners"] > proj["prob_away_more_corners"]
    assert proj["line_probs"]["over_7_5"] > 0.5


def test_build_halftime_report_from_fixture():
    report = build_halftime_report(
        _harju_stats(),
        lambda_full_home=1.2,
        lambda_full_away=1.0,
    )
    assert report is not None
    assert report.applied is True
    assert report.corner_line_probs
    assert "0×0" in report.summary


def test_simulate_inplay_first_half_no_halftime_adjust():
    r = simulate_inplay(
        home_team="Harju Laagri",
        away_team="Kuressaare",
        home_score=0,
        away_score=0,
        minute=30,
        lambda_full_home=1.2,
        lambda_full_away=1.0,
        n_simulations=2000,
        random_seed=42,
        halftime_stats=_harju_stats(),
    )
    assert r.halftime_adjustment is None or r.halftime_adjustment.get("applied") is not True


def test_simulate_inplay_second_half_applies_halftime_adjust():
    stats = _harju_stats()
    kwargs = dict(
        home_team="Harju Laagri",
        away_team="Kuressaare",
        home_score=0,
        away_score=0,
        minute=55,
        ht_home_score=0,
        ht_away_score=0,
        lambda_full_home=1.2,
        lambda_full_away=1.0,
        n_simulations=4000,
        random_seed=99,
        halftime_stats=stats,
        bayesian_update=False,
        momentum_events=[],
    )
    with patch.object(settings, "inplay_halftime_adjust", True):
        r_on = simulate_inplay(**kwargs)
    with patch.object(settings, "inplay_halftime_adjust", False):
        r_off = simulate_inplay(**kwargs)

    assert r_on.halftime_adjustment is not None
    assert r_on.halftime_adjustment.get("applied") is True
    assert abs(r_on.prob_sh_home - r_off.prob_sh_home) > 0.001 or abs(
        r_on.prob_sh_away - r_off.prob_sh_away
    ) > 0.001


def test_aporte_candidates_corners_post_ht():
    inplay = {
        "current_score": "0x0",
        "corner_line_probs": {"over_7_5": 0.62, "under_7_5": 0.38},
    }
    ip = SuperbetInPlayState(
        home_score=0,
        away_score=0,
        minute=50,
        stoppage_time=None,
        home_corners=3,
        away_corners=4,
        home_yellow_cards=2,
        away_yellow_cards=0,
        ht_home_score=0,
        ht_away_score=0,
        period_label="2H",
        status="STARTED",
    )
    snapshot = SuperbetEventSnapshot(
        event_id=13368253,
        home_team="Harju Laagri",
        away_team="Kuressaare",
        event_name="Harju Laagri·Kuressaare",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=ip,
        h2h_odds={"1": 2.0, "X": 3.0, "2": 4.0},
        h2h_implied={"1": 0.4, "X": 0.3, "2": 0.3},
        totals={},
        totals_implied={},
        corners={"7.5": {"Mais de 7.5": 1.85, "Menos de 7.5": 1.95}},
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
        raw_market_count=1,
        captured_at="2026-06-11T01:00:00Z",
    )
    candidates = _aporte_candidates(
        inplay,
        snapshot,
        home_team="Harju Laagri",
        away_team="Kuressaare",
        minute=50,
    )
    markets = [c[0] for c in candidates]
    assert any(m.startswith("corners_over_") for m in markets)


def test_load_from_ticks_handles_pandas_na(tmp_path, monkeypatch):
    import pandas as pd

    ticks_path = tmp_path / "live_poll.parquet"
    df = pd.DataFrame(
        [
            {
                "event_id": 11499850,
                "minute": 46,
                "home_score": pd.NA,
                "away_score": pd.NA,
                "home_corners": pd.NA,
                "away_corners": 2,
                "home_yellow_cards": pd.NA,
                "away_yellow_cards": 1,
                "home_red_cards": pd.NA,
                "away_red_cards": pd.NA,
                "home_team": "Time A",
                "away_team": "Time B",
                "captured_at": pd.Timestamp("2026-06-13T14:00:00Z"),
            }
        ]
    )
    df.to_parquet(ticks_path)
    monkeypatch.setattr(
        "ingest.superbet.halftime_snapshot.live_ticks_path",
        lambda: ticks_path,
    )

    loaded = _load_from_ticks(11499850)
    assert loaded is not None
    assert loaded.ht_home_score == 0
    assert loaded.ht_away_score == 0
    assert loaded.home_corners_1h == 0
    assert loaded.away_corners_1h == 2
    assert loaded.away_yellows_1h == 1


def test_save_and_load_halftime_stats(tmp_path, monkeypatch):
    ht_dir = tmp_path / "bronze" / "superbet" / "halftime"
    monkeypatch.setattr(
        "ingest.superbet.halftime_snapshot._halftime_dir",
        lambda: ht_dir,
    )
    stats = _harju_stats()
    save_halftime_stats(stats)
    loaded = load_halftime_stats(stats.event_id)
    assert loaded is not None
    assert loaded.home_corners_1h == 3
    assert loaded.home_yellows_1h == 2


def test_load_or_freeze_halftime_reuses_json(tmp_path, monkeypatch):
    ht_dir = tmp_path / "bronze" / "superbet" / "halftime"
    monkeypatch.setattr(
        "ingest.superbet.halftime_snapshot._halftime_dir",
        lambda: ht_dir,
    )
    save_halftime_stats(_harju_stats())
    from ingest.superbet.parser import SuperbetEventSnapshot, SuperbetInPlayState

    ip = SuperbetInPlayState(
        home_score=1,
        away_score=0,
        minute=60,
        stoppage_time=None,
        home_corners=99,
        away_corners=99,
        home_yellow_cards=9,
        away_yellow_cards=9,
        ht_home_score=1,
        ht_away_score=0,
        period_label="2H",
        status="STARTED",
    )
    snapshot = SuperbetEventSnapshot(
        event_id=13368253,
        home_team="Harju Laagri",
        away_team="Kuressaare",
        event_name="Harju Laagri·Kuressaare",
        utc_date=None,
        betradar_id=None,
        is_live=True,
        inplay=ip,
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
        raw_market_count=0,
        captured_at="2026-06-11T01:00:00Z",
    )
    frozen = load_or_freeze_halftime(13368253, snapshot)
    assert frozen is not None
    assert frozen.home_corners_1h == 3
    assert frozen.away_corners_1h == 4
