"""Testes: λ ajuste por placar condicionado ao Sofascore + labels sintéticos GBM."""
from __future__ import annotations

import pandas as pd

from models.wc_inplay import _use_score_lambda_adjust, simulate_inplay


class TestScoreLambdaAdjust:
    def test_off_by_default(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust_with_sofascore", True)
        assert not _use_score_lambda_adjust(None)
        assert not _use_score_lambda_adjust([])

    def test_on_with_sofascore_events(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust_with_sofascore", True)
        events = [{"source": "sofascore", "event_type": "goal", "minute": 10, "team": "home"}]
        assert _use_score_lambda_adjust(events)

    def test_simulate_changes_lambda_with_sofascore(self, monkeypatch):
        from config import settings as s

        monkeypatch.setattr(s, "inplay_score_lambda_adjust", False)
        monkeypatch.setattr(s, "inplay_score_lambda_adjust_with_sofascore", True)
        monkeypatch.setattr(s, "inplay_use_nhpp", False)
        monkeypatch.setattr(s, "inplay_use_market_shrinkage", False)
        monkeypatch.setattr(s, "inplay_momentum_on_remaining", False)
        monkeypatch.setattr(s, "wc_mc_simulations", 500)

        base = simulate_inplay(
            home_team="A",
            away_team="B",
            home_score=2,
            away_score=0,
            minute=60,
            lambda_full_home=1.4,
            lambda_full_away=1.2,
            bayesian_update=False,
            momentum_events=None,
            n_simulations=500,
            random_seed=1,
        )
        with_ss = simulate_inplay(
            home_team="A",
            away_team="B",
            home_score=2,
            away_score=0,
            minute=60,
            lambda_full_home=1.4,
            lambda_full_away=1.2,
            bayesian_update=False,
            momentum_events=[{"source": "sofascore", "event_type": "goal"}],
            n_simulations=500,
            random_seed=1,
        )
        assert base.lambda_full_home != with_ss.lambda_full_home


class TestSyntheticFeedback:
    def test_build_from_match_states(self, tmp_path, monkeypatch):
        from config import settings as s
        from pipelines.inplay_synthetic_feedback import build_synthetic_gbm_from_match_states

        monkeypatch.setattr(s, "lake_root", tmp_path)
        # MATCH_STATES_PATH uses settings at import - patch path directly
        path = tmp_path / "silver" / "inplay" / "match_states.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            [
                {
                    "event_id": 1,
                    "minute": 45,
                    "home_score": 1,
                    "away_score": 0,
                    "home_score_final": 2,
                    "away_score_final": 0,
                    "y_final": "1",
                    "prob_final_home": 0.6,
                    "prob_final_away": 0.2,
                },
                {
                    "event_id": 1,
                    "minute": 80,
                    "home_score": 2,
                    "away_score": 0,
                    "home_score_final": 2,
                    "away_score_final": 0,
                    "y_final": "1",
                    "prob_final_home": 0.9,
                    "prob_final_away": 0.05,
                },
            ]
        )
        df.to_parquet(path, index=False)

        import pipelines.inplay_synthetic_feedback as mod

        monkeypatch.setattr(mod, "MATCH_STATES_PATH", path)
        X, y = build_synthetic_gbm_from_match_states()
        assert len(X) == 2
        assert y[0] == 1  # ainda haverá gol home
        assert y[1] == 0  # placar final já atingido

    def test_build_tolerates_pandas_na(self, tmp_path, monkeypatch):
        from config import settings as s
        from pipelines.inplay_synthetic_feedback import build_synthetic_gbm_from_match_states

        monkeypatch.setattr(s, "lake_root", tmp_path)
        path = tmp_path / "silver" / "inplay" / "match_states.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(
            [
                {
                    "event_id": 2,
                    "minute": 30,
                    "home_score": 0,
                    "away_score": 0,
                    "home_score_final": 1,
                    "away_score_final": 0,
                    "y_final": "1",
                    "prob_final_home": pd.NA,
                    "prob_final_away": pd.NA,
                    "home_red_cards": pd.NA,
                    "n_red_cards_ss": pd.NA,
                    "away_red_cards": pd.NA,
                    "home_corners": pd.NA,
                    "away_corners": pd.NA,
                },
            ]
        )
        df.to_parquet(path, index=False)

        import pipelines.inplay_synthetic_feedback as mod

        monkeypatch.setattr(mod, "MATCH_STATES_PATH", path)
        X, y = build_synthetic_gbm_from_match_states()
        assert len(X) == 1
        assert X[0, 7] == 0.0
        assert X[0, 9] == 0.0
