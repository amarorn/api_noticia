"""Testes do modelo in-play de basquete."""
from __future__ import annotations

import pytest

from models.basket_inplay import simulate_basket_inplay


class TestSimulateBasketInPlay:
    def test_pre_game_moneyline_sums_to_one(self):
        result = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=0,
            away_score=0,
            minute=0,
            moneyline_odds={"1": 1.80, "2": 2.05},
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        )
        total = result.prob_home_win + result.prob_away_win
        assert 0.97 <= total <= 1.03

    def test_favorite_leading_increases_win_prob(self):
        result = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=60,
            away_score=50,
            minute=24,
            moneyline_odds={"1": 1.75, "2": 2.10},
            spread_odds={"m5_5": {"home": 1.90, "away": 1.90}},
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        )
        assert result.prob_home_win > result.prob_away_win

    def test_total_line_already_guaranteed(self):
        # Placar atual 120x110 = 230 total; over 220.5 é certo, under 220.5 é 0
        result = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=120,
            away_score=110,
            minute=46,
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
        )
        assert result.total_probs["over_220_5"] == pytest.approx(1.0, abs=1e-6)
        assert result.total_probs["under_220_5"] == pytest.approx(0.0, abs=1e-6)

    def test_expected_total_near_market_line(self):
        result = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=55,
            away_score=55,
            minute=24,
            match_minutes=48,  # cenário NBA (linha de mercado 220.5 é escala NBA, não virtual/40min)
            total_points_odds={"220.5": {"over": 1.90, "under": 1.90}},
            spread_odds={"0": {"home": 1.90, "away": 1.90}},
        )
        # Espera-se que o total final fique razoavelmente próximo da linha de mercado
        assert 200 <= result.expected_total <= 240

    def test_spread_cover_probabilities_sum(self):
        result = simulate_basket_inplay(
            home_team="LAL",
            away_team="GSW",
            home_score=50,
            away_score=50,
            minute=24,
            spread_odds={"m5_5": {"home": 1.90, "away": 1.90}},
        )
        for line_key in result.spread_probs:
            if "_" not in line_key:
                continue
            prefix, _ = line_key.rsplit("_", 1)
            if prefix not in {"home", "away"}:
                continue
            # Só verificamos linhas pares home/away explicitamente no dict
        home_m5_5 = result.spread_probs.get("home_m5_5", 0.0)
        away_m5_5 = result.spread_probs.get("away_m5_5", 0.0)
        assert 0.97 <= home_m5_5 + away_m5_5 <= 1.03
