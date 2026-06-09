"""Testes para Fase 2 — calibração MLE do momentum e NHPP."""
from __future__ import annotations

import pytest

from models.wc_inplay_coefficients import (
    InPlayCoefficients,
    MomentumBeta,
    NHPPWeight,
    save_inplay_coefficients,
    load_inplay_coefficients,
)
from models.wc_live_momentum import (
    MomentumContext,
    GameEvent,
    compute_momentum,
    compute_momentum_calibrated,
)
from pipelines.wc_intensity_profile import (
    compute_remaining_lambda,
    validate_profile,
    default_intensity_profile,
)


class TestInPlayCoefficients:
    """Testes da persistência de coeficientes."""

    def test_round_trip_json(self, tmp_path):
        coefs = InPlayCoefficients(
            momentum_betas=[
                MomentumBeta("goal_diff", 0.06, 0.02),
                MomentumBeta("late_game", -0.15, 0.10),
            ],
            nhpp_weights=[NHPPWeight(0, 15, 0.84, 0.05)],
            train_seasons=[2018, 2022],
            n_observations=500,
        )
        path = tmp_path / "coefs.json"
        save_inplay_coefficients(coefs, path)
        loaded = load_inplay_coefficients(path)
        assert loaded is not None
        assert len(loaded.momentum_betas) == 2
        assert loaded.get_beta("goal_diff") == 0.06
        assert loaded.train_seasons == [2018, 2022]

    def test_significance(self):
        beta = MomentumBeta("test", 0.1, 0.04)  # z = 2.5 → significativo
        assert beta.significant is True
        beta2 = MomentumBeta("test2", 0.05, 0.10)  # z = 0.5 → não
        assert beta2.significant is False

    def test_missing_file_returns_none(self, tmp_path):
        result = load_inplay_coefficients(tmp_path / "nao_existe.json")
        assert result is None


class TestMomentumCalibrated:
    """Testes do momentum calibrado."""

    def test_fallback_sem_coeficientes(self):
        """Sem arquivo de coeficientes, deve usar momentum default."""
        ctx = MomentumContext(
            home_score=1, away_score=0, minute=60,
            match_minutes=90, events=[],
        )
        result = compute_momentum_calibrated(ctx)
        # Deve retornar resultado válido (fallback)
        assert 0.5 <= result.home_factor <= 1.5
        assert 0.5 <= result.away_factor <= 1.5

    def test_momentum_default_funciona(self):
        """Momentum default (constantes Fase 1) produz resultado razoável."""
        ctx = MomentumContext(
            home_score=2, away_score=0, minute=75,
            match_minutes=90, events=[
                GameEvent("red_card", 65, "away"),
            ],
        )
        result = compute_momentum(ctx)
        # Time na frente com adversário com vermelho:
        # home_factor pode cair (time na frente recua) mas não drasticamente
        assert result.home_factor > 0.5
        assert result.away_factor > 0.5

    def test_nhpp_profile_valido(self):
        profile = default_intensity_profile()
        assert validate_profile(profile)

    def test_remaining_lambda_decreases(self):
        """λ_remaining deve diminuir com o tempo."""
        lam_0 = compute_remaining_lambda(1.5, 0)
        lam_30 = compute_remaining_lambda(1.5, 30)
        lam_60 = compute_remaining_lambda(1.5, 60)
        lam_85 = compute_remaining_lambda(1.5, 85)
        assert lam_0 > lam_30 > lam_60 > lam_85 > 0


class TestBuildTimeline:
    """Testes do pipeline de timeline."""

    def test_timeline_build(self):
        from pipelines.wc_build_timeline import build_timeline_from_fixtures
        df = build_timeline_from_fixtures(min_season=2022, max_season=2022)
        if df.empty:
            pytest.skip("Sem fixtures WC 2022 disponíveis")
        assert "match_id" in df.columns
        assert "remaining_goals_home" in df.columns
        assert "minute" in df.columns
        # Gols restantes nunca negativos
        assert (df["remaining_goals_home"] >= 0).all()
        assert (df["remaining_goals_away"] >= 0).all()
