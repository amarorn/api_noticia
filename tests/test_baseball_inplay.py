"""Testes do modelo in-play de beisebol."""
from __future__ import annotations

import pytest

from models.baseball_inplay import simulate_baseball_inplay


class TestSimulateBaseballInPlay:
    def test_pre_game_moneyline_sums_to_one(self):
        result = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=0,
            away_score=0,
            inning=1,
            moneyline_odds={"1": 1.85, "2": 2.00},
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            n_simulations=2000,
            random_seed=42,
        )
        total = result.prob_home_win + result.prob_away_win
        assert 0.97 <= total <= 1.03

    def test_favorite_leading_late_increases_win_prob(self):
        result = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=5,
            away_score=1,
            inning=7,
            moneyline_odds={"1": 1.40, "2": 2.90},
            spread_odds={"m1_5": {"home": 1.90, "away": 1.90}},
            n_simulations=2000,
            random_seed=7,
        )
        assert result.prob_home_win > result.prob_away_win
        assert result.prob_home_win > 0.75

    def test_total_already_guaranteed_over(self):
        result = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=7,
            away_score=6,
            inning=8,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            n_simulations=1500,
            random_seed=1,
        )
        assert result.total_probs["over_8_5"] == pytest.approx(1.0, abs=1e-6)

    def test_expected_total_near_market(self):
        result = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=2,
            away_score=2,
            inning=4,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            n_simulations=3000,
            random_seed=3,
        )
        assert 6.0 <= result.expected_total <= 12.0

    def test_box_score_adapt_raises_projection_on_high_scoring(self, monkeypatch):
        monkeypatch.setattr("config.settings.baseball_box_score_adapt", True)
        monkeypatch.setattr("config.settings.baseball_box_score_weight_boost", 1.5)
        innings = [
            {"num": 1, "home": 2, "away": 0},
            {"num": 2, "home": 3, "away": 1},
            {"num": 3, "home": 1, "away": 0},
            {"num": 4, "home": 2, "away": 0},
        ]
        high = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=8,
            away_score=1,
            inning=4,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            innings_observed=innings,
            n_simulations=2500,
            random_seed=11,
        )
        low = simulate_baseball_inplay(
            home_team="NYY",
            away_team="BOS",
            home_score=2,
            away_score=2,
            inning=4,
            total_runs_odds={"8.5": {"over": 1.90, "under": 1.90}},
            n_simulations=2500,
            random_seed=11,
        )
        assert high.score_adapted is True
        assert high.expected_total > low.expected_total + 2.0
