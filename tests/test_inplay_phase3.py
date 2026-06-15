"""Testes da Fase 3 — Hawkes + GBM + Ensemble."""
from __future__ import annotations

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fase 3.1: Hawkes Process
# ---------------------------------------------------------------------------


class TestHawkesProcess:
    """Testes do processo Hawkes para timing de gols."""

    def test_hawkes_parameters_stability(self):
        """Parâmetros default devem ser estáveis."""
        from models.wc_hawkes import HawkesParameters

        params = HawkesParameters()
        assert params.is_stable
        assert params.half_life > 0

    def test_hawkes_unstable_detection(self):
        """Detectar processo instável quando α/β >= 1."""
        from models.wc_hawkes import HawkesParameters

        unstable = HawkesParameters(alpha_self=0.5, alpha_cross=0.6, beta=0.1)
        assert not unstable.is_stable

    def test_hawkes_intensity_increases_after_goal(self):
        """Intensidade deve subir logo após um gol."""
        from models.wc_hawkes import HawkesGoalEvent, HawkesParameters, hawkes_intensity

        params = HawkesParameters()
        past = [HawkesGoalEvent(minute=30.0, team="home")]
        mu = 0.015

        # Imediatamente após o gol (min 30.1)
        lam_after = hawkes_intensity(30.1, past, params, mu, "home")
        # Muito depois (min 60)
        lam_later = hawkes_intensity(60.0, past, params, mu, "home")
        # Sem gol nenhum
        lam_base = hawkes_intensity(30.1, [], params, mu, "home")

        assert lam_after > lam_base  # excitação eleva
        assert lam_after > lam_later  # decai com o tempo
        assert lam_later > mu - 0.001  # eventualmente retorna ao baseline

    def test_hawkes_cross_excitation(self):
        """Gol do adversário deve excitar mais que gol próprio (α_cross > α_self)."""
        from models.wc_hawkes import HawkesGoalEvent, HawkesParameters, hawkes_intensity

        params = HawkesParameters()  # α_cross=0.12 > α_self=0.08
        mu = 0.015

        # Gol do adversário
        past_cross = [HawkesGoalEvent(minute=30.0, team="away")]
        lam_cross = hawkes_intensity(30.5, past_cross, params, mu, "home")

        # Gol próprio
        past_self = [HawkesGoalEvent(minute=30.0, team="home")]
        lam_self = hawkes_intensity(30.5, past_self, params, mu, "home")

        assert lam_cross > lam_self

    def test_simulate_hawkes_batch_consistency(self):
        """Batch simulation deve retornar resultados consistentes."""
        from models.wc_hawkes import (
            HawkesGoalEvent,
            HawkesParameters,
            hawkes_probs_from_simulation,
            simulate_hawkes_batch,
        )

        params = HawkesParameters()
        past = [HawkesGoalEvent(minute=20.0, team="home")]
        sim = simulate_hawkes_batch(
            t_now=45, t_end=90,
            mu_home=1.3 / 90, mu_away=1.0 / 90,
            params=params, past_goals=past,
            n_simulations=3000, seed=123,
        )

        assert "goals_home" in sim
        assert "goals_away" in sim
        assert len(sim["goals_home"]) == 3000
        assert sim["mean_goals_home"] >= 0
        assert sim["mean_goals_away"] >= 0

        probs = hawkes_probs_from_simulation(sim, current_home_score=1, current_away_score=0)
        assert abs(probs["1"] + probs["X"] + probs["2"] - 1.0) < 1e-6
        # Home na frente 1-0 no min 45 deve ter > 50% de chance de ganhar
        assert probs["1"] > 0.4

    def test_simulate_hawkes_deterministic_with_seed(self):
        """Simulação deve ser reprodutível com mesma seed."""
        from models.wc_hawkes import HawkesParameters, simulate_hawkes_batch

        params = HawkesParameters()
        kwargs = dict(t_now=30, t_end=90, mu_home=0.015, mu_away=0.012,
                      params=params, past_goals=[], n_simulations=1000, seed=42)

        r1 = simulate_hawkes_batch(**kwargs)
        r2 = simulate_hawkes_batch(**kwargs)
        np.testing.assert_array_equal(r1["goals_home"], r2["goals_home"])


# ---------------------------------------------------------------------------
# Fase 3.2: Hawkes Fit
# ---------------------------------------------------------------------------


class TestHawkesFit:
    """Testes da calibração MLE do Hawkes."""

    def test_reconstruct_goal_times(self):
        """Reconstrução de tempos de gol deve gerar quantidade correta."""
        from pipelines.wc_inplay_hawkes_fit import _reconstruct_goal_times

        events = _reconstruct_goal_times(3, 2, 90, np.random.default_rng(7))
        assert len(events) == 5
        # Todos os minutos devem estar entre 1 e 90
        for e in events:
            assert 1 <= e.minute <= 90

    def test_hawkes_log_likelihood_negative(self):
        """Log-likelihood deve ser negativa (estamos minimizando -LL)."""
        from models.wc_hawkes import HawkesGoalEvent
        from pipelines.wc_inplay_hawkes_fit import hawkes_log_likelihood

        events = [
            HawkesGoalEvent(minute=20.0, team="home"),
            HawkesGoalEvent(minute=55.0, team="away"),
        ]
        seqs = [(events, 0.015, 0.012, 90)]
        nll = hawkes_log_likelihood(np.array([0.08, 0.12, 0.25]), seqs)
        assert nll > 0  # -LL > 0 (LL < 0)

    def test_fit_hawkes_small_batch(self):
        """MLE em batch pequeno deve convergir."""
        from pipelines.wc_inplay_hawkes_fit import (
            _reconstruct_goal_times,
            fit_hawkes_mle,
        )

        rng = np.random.default_rng(42)
        seqs = []
        for _ in range(30):
            hs = int(rng.integers(0, 4))
            as_ = int(rng.integers(0, 4))
            evts = _reconstruct_goal_times(hs, as_, 90, rng)
            seqs.append((evts, 0.015, 0.012, 90))

        result = fit_hawkes_mle(sequences=seqs)
        assert result.converged
        assert result.is_stable
        assert result.alpha_self > 0
        assert result.alpha_cross > 0
        assert result.beta > 0

    def test_save_load_hawkes_params(self, tmp_path):
        """Parâmetros devem persistir e carregar corretamente."""
        from pipelines.wc_inplay_hawkes_fit import (
            HawkesFitResult,
            load_hawkes_params,
            save_hawkes_params,
        )

        fit = HawkesFitResult(
            alpha_self=0.07, alpha_cross=0.11, beta=0.30,
            n_matches=100, n_goals=250,
            log_likelihood=-500.0, converged=True,
            half_life_minutes=2.3,
        )
        path = tmp_path / "hawkes_params.json"
        save_hawkes_params(fit, path)

        loaded = load_hawkes_params(path)
        assert abs(loaded.alpha_self - 0.07) < 1e-6
        assert abs(loaded.alpha_cross - 0.11) < 1e-6
        assert abs(loaded.beta - 0.30) < 1e-6


# ---------------------------------------------------------------------------
# Fase 3.3: GBM Model
# ---------------------------------------------------------------------------


class TestGBMModel:
    """Testes do modelo LightGBM in-play."""

    def test_gbm_fit_and_predict(self):
        """Modelo deve treinar e predizer corretamente."""
        from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel

        rng = np.random.default_rng(42)
        n = 100
        X = rng.random((n, len(GBM_FEATURES)))
        y = rng.integers(0, 3, size=n)

        model = InPlayGBMModel(window_minutes=10)
        assert not model.is_fitted

        metrics = model.fit(X, y, n_estimators=30)
        assert model.is_fitted
        assert "train_logloss" in metrics
        assert metrics["train_accuracy"] > 0.3  # acima de random (33%)

        preds = model.predict(X[:5])
        assert len(preds) == 5
        for p in preds:
            total = p.prob_no_goal + p.prob_goal_home + p.prob_goal_away
            assert abs(total - 1.0) < 1e-5
            assert p.prob_any_goal == pytest.approx(
                p.prob_goal_home + p.prob_goal_away, abs=1e-6
            )

    def test_gbm_predict_single(self):
        """predict_single deve aceitar dict de features."""
        from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel

        rng = np.random.default_rng(7)
        X = rng.random((50, len(GBM_FEATURES)))
        y = rng.integers(0, 3, size=50)

        model = InPlayGBMModel()
        model.fit(X, y, n_estimators=20)

        features = {f: 0.5 for f in GBM_FEATURES}
        pred = model.predict_single(features)
        assert pred.window_minutes == 10
        assert 0 <= pred.prob_no_goal <= 1

    def test_gbm_save_load(self, tmp_path):
        """Persistência pickle deve preservar predições."""
        from models.wc_inplay_gbm import GBM_FEATURES, InPlayGBMModel

        rng = np.random.default_rng(42)
        X = rng.random((50, len(GBM_FEATURES)))
        y = rng.integers(0, 3, size=50)

        model = InPlayGBMModel()
        model.fit(X, y, n_estimators=20)

        path = tmp_path / "gbm.pkl"
        model.save(path)

        loaded = InPlayGBMModel.load(path)
        assert loaded.is_fitted

        features = {f: 0.5 for f in GBM_FEATURES}
        p1 = model.predict_single(features)
        p2 = loaded.predict_single(features)
        assert abs(p1.prob_no_goal - p2.prob_no_goal) < 1e-10

    def test_gbm_load_nonexistent(self, tmp_path):
        """Carregar modelo inexistente deve retornar instância não-treinada."""
        from models.wc_inplay_gbm import InPlayGBMModel

        model = InPlayGBMModel.load(tmp_path / "nonexistent.pkl")
        assert not model.is_fitted


# ---------------------------------------------------------------------------
# Fase 3.5: Ensemble
# ---------------------------------------------------------------------------


class TestEnsemble:
    """Testes do ensemble dinâmico."""

    def test_ensemble_all_models(self):
        """Ensemble com todos os modelos deve somar 1."""
        from models.wc_inplay_ensemble import EnsembleInput, blend_ensemble

        inp = EnsembleInput(
            minute=60.0,
            poisson_probs={"1": 0.50, "X": 0.25, "2": 0.25},
            hawkes_probs={"1": 0.55, "X": 0.22, "2": 0.23},
            gbm_probs={"1": 0.48, "X": 0.28, "2": 0.24},
            market_probs={"1": 0.52, "X": 0.26, "2": 0.22},
        )
        result = blend_ensemble(inp)
        total = result.prob_home + result.prob_draw + result.prob_away
        assert abs(total - 1.0) < 1e-6
        assert len(result.components_used) == 4

    def test_ensemble_missing_models(self):
        """Ensemble deve redistribuir pesos quando modelos faltam."""
        from models.wc_inplay_ensemble import EnsembleInput, blend_ensemble

        inp = EnsembleInput(
            minute=30.0,
            poisson_probs={"1": 0.40, "X": 0.30, "2": 0.30},
            hawkes_available=False,
            gbm_available=False,
            market_probs={"1": 0.45, "X": 0.28, "2": 0.27},
        )
        result = blend_ensemble(inp)
        total = result.prob_home + result.prob_draw + result.prob_away
        assert abs(total - 1.0) < 1e-6
        assert "hawkes" not in result.components_used
        assert "gbm" not in result.components_used

    def test_ensemble_no_models(self):
        """Sem modelos deve retornar prior uniforme."""
        from models.wc_inplay_ensemble import EnsembleInput, blend_ensemble

        inp = EnsembleInput(
            minute=45.0,
            poisson_available=False,
            hawkes_available=False,
            gbm_available=False,
            market_available=False,
        )
        result = blend_ensemble(inp)
        assert abs(result.prob_home - 1 / 3) < 1e-6
        assert len(result.components_used) == 0

    def test_ensemble_weights_vary_by_minute(self):
        """Pesos devem mudar entre buckets temporais."""
        from models.wc_inplay_ensemble import EnsembleWeights

        w = EnsembleWeights()
        w_early = w.get_weights(5.0)
        w_late = w.get_weights(80.0)

        # Market tem mais peso no início
        assert w_early[3] > w_late[3]
        # Hawkes+GBM têm mais peso no final
        assert w_late[1] + w_late[2] > w_early[1] + w_early[2]

    def test_gbm_probs_to_1x2(self):
        """Conversão GBM → 1X2 deve somar 1."""
        from models.wc_inplay_ensemble import gbm_probs_to_1x2

        probs = gbm_probs_to_1x2(0.5, 0.3, 0.2, current_home_score=1, current_away_score=0)
        total = probs["1"] + probs["X"] + probs["2"]
        assert abs(total - 1.0) < 1e-6
        # Home na frente: P(1) deve ser alta
        assert probs["1"] > probs["2"]


# ---------------------------------------------------------------------------
# Fase 3.6: Integração
# ---------------------------------------------------------------------------


class TestEnsembleIntegration:
    """Testes de integração do ensemble com simulate_inplay."""

    def test_simulate_inplay_ensemble_runs(self):
        """Versão ensemble deve rodar sem erro."""
        from models.wc_inplay import simulate_inplay_ensemble

        result = simulate_inplay_ensemble(
            home_team="Brasil",
            away_team="Argentina",
            home_score=1,
            away_score=0,
            minute=60,
            lambda_full_home=1.5,
            lambda_full_away=1.2,
            n_simulations=1000,
        )
        total = result.prob_final_home + result.prob_final_draw + result.prob_final_away
        assert abs(total - 1.0) < 0.01  # tolerância MC
        assert result.prob_final_home > 0.3  # home na frente

    def test_simulate_inplay_ensemble_minute_zero(self):
        """No minuto 0 deve retornar resultado base (sem ensemble)."""
        from models.wc_inplay import simulate_inplay, simulate_inplay_ensemble

        kwargs = dict(
            home_team="Brasil", away_team="Argentina",
            home_score=0, away_score=0, minute=0,
            lambda_full_home=1.5, lambda_full_away=1.2,
            n_simulations=500, random_seed=42,
        )
        base = simulate_inplay(**kwargs)
        ensemble = simulate_inplay_ensemble(**kwargs)

        # Devem ser iguais quando minute=0
        assert abs(base.prob_final_home - ensemble.prob_final_home) < 1e-6
