"""Testes para ajuste H2H in-play (wc_inplay_h2h_adjust)."""
from __future__ import annotations

import pytest

from models.wc_inplay_h2h_adjust import (
    H2HAdjust,
    apply_h2h_adjust,
    compute_h2h_adjust,
    parse_h2h_from_context,
)


class TestParseH2HFromContext:
    """Testa extração de dados H2H do match_context."""

    def test_none_context(self):
        assert parse_h2h_from_context(None) is None

    def test_empty_context(self):
        assert parse_h2h_from_context({}) is None

    def test_txt_report_format(self):
        ctx = {
            "h2h": {
                "total": 3,
                "home_wins": 3,
                "draws": 0,
                "away_wins": 0,
                "home_goals": 15,
                "away_goals": 1,
                "avg_total_goals": 5.33,
            }
        }
        result = parse_h2h_from_context(ctx)
        assert result is not None
        assert result["total"] == 3
        assert result["home_wins"] == 3
        assert result["avg_total_goals"] == 5.33

    def test_txt_report_insufficient_games(self):
        ctx = {"h2h": {"total": 1, "home_wins": 1}}
        assert parse_h2h_from_context(ctx) is None

    def test_scorealarm_format(self):
        ctx = {
            "home_team": "Brasil",
            "away_team": "Haiti",
            "scorealarm": {
                "h2h": {"total": 5, "home_wins": 4, "draws": 1, "away_wins": 0}
            },
        }
        result = parse_h2h_from_context(ctx)
        assert result is not None
        assert result["total"] == 5
        assert result["home_wins"] == 4
        assert result["home_goals"] == 0  # ScoreAlarm não tem gols

    def test_no_h2h_data(self):
        ctx = {"referee_card_lambda": 4.5}
        assert parse_h2h_from_context(ctx) is None


class TestComputeH2HAdjust:
    """Testa computação do ajuste H2H."""

    @pytest.fixture
    def brasil_haiti_h2h(self):
        """H2H real: Brasil 3/3 vs Haiti, 15-1 gols, média 5.33."""
        return {
            "total": 3,
            "home_wins": 3,
            "draws": 0,
            "away_wins": 0,
            "home_goals": 15,
            "away_goals": 1,
            "avg_total_goals": 5.33,
        }

    def test_insufficient_history(self):
        h2h = {"total": 1, "home_wins": 1, "draws": 0, "away_wins": 0}
        adj = compute_h2h_adjust(h2h, "A", "B", 0, 0, 30, 1.5, 1.2)
        assert not adj.applied
        assert adj.lambda_home_factor == 1.0
        assert adj.reason == "histórico insuficiente"

    def test_no_adjust_when_winning(self, brasil_haiti_h2h):
        """Brasil dominando H2H e VENCENDO → só ajuste de gols, não comeback."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 2, 0, 30, 2.1, 1.4)
        assert adj.applied
        # Sem comeback boost (Brasil já vence), mas tem boost de gols H2H alto
        assert adj.lambda_home_factor > 1.0
        assert adj.lambda_away_factor > 1.0
        assert "comeback" not in adj.reason
        assert "H2H aberto" in adj.reason

    def test_comeback_boost_when_losing(self, brasil_haiti_h2h):
        """Brasil dominando H2H mas PERDENDO → comeback boost."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 1, 30, 2.1, 1.4)
        assert adj.applied
        assert adj.lambda_home_factor > 1.03
        assert "comeback boost Brasil" in adj.reason
        assert "domina H2H 3/3" in adj.reason

    def test_comeback_boost_stronger_when_losing_by_2(self, brasil_haiti_h2h):
        """Perdendo por 2 gols → boost maior (mas capped)."""
        adj1 = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 1, 30, 2.1, 1.4)
        adj2 = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 2, 30, 2.1, 1.4)
        assert adj2.lambda_home_factor > adj1.lambda_home_factor
        assert adj2.lambda_home_factor <= 1.15  # hard cap

    def test_draw_suppression(self, brasil_haiti_h2h):
        """H2H sem empates → draw_penalty > 0."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 0, 30, 2.1, 1.4)
        assert adj.draw_penalty > 0.0
        assert "draw suppression" in adj.reason

    def test_high_goals_boost(self, brasil_haiti_h2h):
        """Média 5.33 gols/jogo → boost em ambos λ."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 0, 30, 2.1, 1.4)
        assert adj.lambda_home_factor > 1.0
        assert adj.lambda_away_factor > 1.0
        assert "H2H aberto" in adj.reason

    def test_low_goals_penalty(self):
        """H2H fechado (média 1.5 gols) → penaliza ambos λ."""
        h2h = {
            "total": 4,
            "home_wins": 2,
            "draws": 2,
            "away_wins": 0,
            "home_goals": 3,
            "away_goals": 3,
            "avg_total_goals": 1.5,
        }
        adj = compute_h2h_adjust(h2h, "A", "B", 0, 0, 30, 1.5, 1.2)
        assert adj.lambda_home_factor < 1.0
        assert adj.lambda_away_factor < 1.0
        assert "H2H fechado" in adj.reason

    def test_decay_after_60_minutes(self, brasil_haiti_h2h):
        """Após 60 min, H2H pesa menos."""
        adj_early = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 1, 30, 2.1, 1.4)
        adj_late = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 1, 75, 2.1, 1.4)
        # Boost deve ser menor no late (decay)
        assert adj_late.lambda_home_factor < adj_early.lambda_home_factor
        assert "decay H2H" in adj_late.reason

    def test_decay_at_90_min(self, brasil_haiti_h2h):
        """Aos 90 min, H2H pesa 25% no máximo."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 0, 1, 90, 2.1, 1.4)
        assert "decay H2H 25%" in adj.reason

    def test_away_dominance_comeback(self):
        """Fora domina H2H mas está perdendo → boost fora."""
        h2h = {
            "total": 4,
            "home_wins": 0,
            "draws": 0,
            "away_wins": 4,
            "home_goals": 2,
            "away_goals": 10,
            "avg_total_goals": 3.0,
        }
        # Casa vencendo 1-0, fora domina H2H
        adj = compute_h2h_adjust(h2h, "A", "B", 1, 0, 30, 1.5, 2.0)
        assert adj.applied
        assert adj.lambda_away_factor >= 1.03
        assert "comeback boost B" in adj.reason

    def test_no_draw_suppression_when_many_draws(self):
        """H2H com muitos empates → sem draw suppression."""
        h2h = {
            "total": 10,
            "home_wins": 3,
            "draws": 4,
            "away_wins": 3,
            "home_goals": 15,
            "away_goals": 15,
            "avg_total_goals": 3.0,
        }
        adj = compute_h2h_adjust(h2h, "A", "B", 0, 0, 30, 1.5, 1.5)
        assert adj.draw_penalty == 0.0
        assert "draw suppression" not in adj.reason

    def test_no_away_boost_when_home_dominates_and_home_winning(self, brasil_haiti_h2h):
        """Brasil dominando e vencendo → Haiti não recebe boost."""
        adj = compute_h2h_adjust(brasil_haiti_h2h, "Brasil", "Haiti", 2, 0, 30, 2.1, 1.4)
        # Haiti (away) não domina H2H, então não tem comeback boost
        assert adj.lambda_away_factor == 1.06  # só boost de gols H2H alto


class TestApplyH2HAdjust:
    """Testa aplicação do ajuste em λ."""

    def test_no_adjust(self):
        adj = H2HAdjust(
            lambda_home_factor=1.0,
            lambda_away_factor=1.0,
            draw_penalty=0.0,
            applied=False,
            reason="nada",
        )
        lh, la, _ = apply_h2h_adjust(2.0, 1.5, adj)
        assert lh == 2.0
        assert la == 1.5

    def test_apply_factors(self):
        adj = H2HAdjust(
            lambda_home_factor=1.10,
            lambda_away_factor=0.95,
            draw_penalty=0.08,
            applied=True,
            reason="test",
        )
        lh, la, _ = apply_h2h_adjust(2.0, 1.5, adj)
        assert round(lh, 4) == 2.2
        assert round(la, 4) == 1.425


class TestIntegration:
    """Testa fluxo completo: parse → compute → apply."""

    def test_brasil_haiti_full_flow(self):
        ctx = {
            "h2h": {
                "total": 3,
                "home_wins": 3,
                "draws": 0,
                "away_wins": 0,
                "home_goals": 15,
                "away_goals": 1,
                "avg_total_goals": 5.33,
            }
        }
        h2h_data = parse_h2h_from_context(ctx)
        assert h2h_data is not None

        adj = compute_h2h_adjust(
            h2h_data, "Brasil", "Haiti", 0, 1, 30, 2.1, 1.4
        )
        assert adj.applied

        lh, la, _ = apply_h2h_adjust(2.1, 1.4, adj)
        assert lh > 2.1  # comeback boost
        assert la > 1.4  # gols H2H alto

    def test_scorealarm_full_flow(self):
        ctx = {
            "home_team": "Brasil",
            "away_team": "Haiti",
            "scorealarm": {
                "h2h": {"total": 5, "home_wins": 4, "draws": 1, "away_wins": 0}
            },
        }
        h2h_data = parse_h2h_from_context(ctx)
        assert h2h_data is not None
        assert h2h_data["total"] == 5

        adj = compute_h2h_adjust(
            h2h_data, "Brasil", "Haiti", 0, 1, 30, 2.1, 1.4
        )
        # Sem avg_total_goals, não tem boost de gols
        assert adj.applied
        assert "comeback boost Brasil" in adj.reason
        assert "H2H aberto" not in adj.reason
