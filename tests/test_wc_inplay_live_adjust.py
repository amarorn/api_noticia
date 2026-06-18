"""Testes: ajuste dinâmico de λ in-play (ScoreAlarm / stats ao vivo)."""
from __future__ import annotations

from models.wc_inplay import _use_score_lambda_adjust, simulate_inplay
from models.wc_inplay_live_adjust import (
    adjust_lambdas_from_live_stats,
    apply_trailing_chase_boost,
    build_lambda_adjustment_report,
    scorealarm_timeline_to_momentum_events,
)


class TestScorealarmTimeline:
    def test_converts_goal_and_corner(self):
        timeline = [
            {"type": 4, "side": 1, "minute": 23, "label": "Gol"},
            {"type": 14, "side": 2, "minute": 40},
        ]
        events = scorealarm_timeline_to_momentum_events(timeline)
        assert len(events) == 2
        assert events[0]["event_type"] == "goal"
        assert events[0]["team"] == "home"
        assert events[0]["source"] == "scorealarm"
        assert events[1]["event_type"] == "corner"
        assert events[1]["team"] == "away"


class TestLiveStatsAdjust:
    def test_possession_shifts_lambda(self):
        out_h, out_a, meta = adjust_lambdas_from_live_stats(
            1.3,
            1.1,
            live_stats={
                "home_possession_pct": 62.0,
                "away_possession_pct": 38.0,
                "home_shots_on_target": 4,
                "away_shots_on_target": 1,
            },
        )
        assert meta["applied"]
        assert out_h > 1.3
        assert out_a < 1.1

    def test_no_stats_no_change(self):
        out_h, out_a, meta = adjust_lambdas_from_live_stats(1.2, 1.0, live_stats=None)
        assert not meta["applied"]
        assert out_h == 1.2
        assert out_a == 1.0


class TestTrailingChase:
    def test_boost_trailing_team_after_recent_goal(self):
        timeline = [{"type": 4, "side": 1, "minute": 70}]
        lam_h, lam_a, meta = apply_trailing_chase_boost(
            0.8,
            0.6,
            minute=75,
            home_score=2,
            away_score=1,
            timeline=timeline,
        )
        assert meta is not None
        assert meta["team"] == "away"
        assert lam_a > 0.6
        assert lam_h == 0.8


class TestLambdaReport:
    def test_report_when_delta_significant(self):
        report = build_lambda_adjustment_report(
            lambda_prior_home=1.4,
            lambda_prior_away=1.2,
            lambda_full_home=1.55,
            lambda_full_away=1.05,
            steps=[{"step": "live_stats", "applied": True}],
        )
        assert report is not None
        assert report["delta_home"] > 0
        assert report["delta_away"] < 0


class TestSimulateInplayIntegration:
    def _base_kwargs(self) -> dict:
        return dict(
            home_team="Brasil",
            away_team="Argentina",
            home_score=1,
            away_score=0,
            minute=55,
            lambda_full_home=1.5,
            lambda_full_away=1.3,
            bayesian_update=False,
            n_simulations=400,
            random_seed=7,
        )

    def test_scorealarm_momentum_enables_score_adjust(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust_with_sofascore", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust_with_scorealarm", True)
        events = [{"source": "scorealarm", "event_type": "goal", "minute": 10, "team": "home"}]
        assert _use_score_lambda_adjust(events)

    def test_live_stats_produces_lambda_adjustment(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_live_stats_lambda_adjust", True)
        monkeypatch.setattr(s, "inplay_use_nhpp", False)
        monkeypatch.setattr(s, "inplay_use_market_shrinkage", False)
        monkeypatch.setattr(s, "inplay_momentum_on_remaining", False)
        monkeypatch.setattr(s, "inplay_trailing_chase_boost", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "wc_mc_simulations", 400)

        result = simulate_inplay(
            **self._base_kwargs(),
            live_stats={
                "home_possession_pct": 65.0,
                "away_possession_pct": 35.0,
                "home_shots_on_target": 5,
                "away_shots_on_target": 1,
            },
        )
        assert result.lambda_adjustment is not None
        assert result.lambda_full_home > 1.5

    def test_trailing_chase_in_lambda_steps(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_trailing_chase_boost", True)
        monkeypatch.setattr(s, "inplay_live_stats_lambda_adjust", False)
        monkeypatch.setattr(s, "inplay_use_nhpp", False)
        monkeypatch.setattr(s, "inplay_use_market_shrinkage", False)
        monkeypatch.setattr(s, "inplay_momentum_on_remaining", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "wc_mc_simulations", 400)

        result = simulate_inplay(
            **self._base_kwargs(),
            live_timeline=[{"type": 4, "side": 1, "minute": 50}],
        )
        steps = (result.lambda_adjustment or {}).get("steps") or []
        assert any(s.get("source") == "trailing_chase" for s in steps)
