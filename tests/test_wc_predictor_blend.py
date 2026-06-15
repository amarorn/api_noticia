"""Testes leves do WcPredictor (blend/seleção sem retreino completo)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from models.wc_model_selection import resolve_blend_weights


def test_resolve_blend_auto_uses_saved_selection(tmp_path, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "lake_root", tmp_path)
    monkeypatch.setattr(settings, "wc_model_selection_mode", "auto")

    sel_dir = tmp_path / "artifacts"
    sel_dir.mkdir(parents=True)
    (sel_dir / "model_selection.json").write_text(
        '{"selected_model":"poisson","blend_weights":{"dixon_coles":1.0,"logistic":0.0}}',
        encoding="utf-8",
    )

    dc, lg, meta = resolve_blend_weights(0.0, 1.0)
    assert dc == 1.0
    assert lg == 0.0
    assert meta["selected_model"] == "poisson"


def test_predict_applies_blend_weights(monkeypatch):
    """Garante que predict() usa pesos da seleção automática."""
    from models.wc_predictor import WcPredictor

    fixtures = pd.DataFrame(
        [
            {
                "season": 2022,
                "match_date": "2022-06-01",
                "home_team": "Brasil",
                "away_team": "Alemanha",
                "home_score": 2,
                "away_score": 1,
                "label": "1",
                "phase": "group",
                "is_neutral": True,
            }
        ]
    )

    predictor = WcPredictor.__new__(WcPredictor)
    predictor.fixtures = fixtures
    predictor._metrics = {"holdout_accuracy": 0.5}
    predictor._dc_metrics = {"rho": 0.0}
    predictor.collab_metrics = MagicMock(brier_score=0.18)
    predictor._draw_metrics = MagicMock(draw_rate=0.2)

    poisson_pred = MagicMock(prob_home=0.6, prob_draw=0.2, prob_away=0.2, most_likely_score="2-1", expected_home_goals=1.5, expected_away_goals=1.0)
    logistic_pred = MagicMock(prob_home=0.4, prob_draw=0.3, prob_away=0.3, prediction="1")

    predictor.dixon_coles = MagicMock()
    predictor.dixon_coles.predict.return_value = poisson_pred
    predictor.dixon_coles.rho = 0.0

    predictor.logistic = MagicMock()
    predictor.logistic.predict_match.return_value = logistic_pred

    predictor.collaborative = MagicMock(dixon_coles_weight=0.5, logistic_weight=0.5)
    predictor.draw_model = MagicMock()
    predictor.draw_model.predict_draw_prob.return_value = 0.25
    predictor.calibrator = MagicMock(is_fitted=False)

    features = MagicMock(home_team="Brasil", away_team="Alemanha")

    blend_calls: list[tuple[float, float]] = []

    def _capture_blend(default_dc: float, default_lg: float):
        blend_calls.append((default_dc, default_lg))
        return 1.0, 0.0, {"mode": "auto", "selected_model": "poisson"}

    monkeypatch.setattr("models.wc_model_selection.resolve_blend_weights", _capture_blend)
    monkeypatch.setattr("models.wc_predictor.build_match_features", lambda *a, **k: features)
    monkeypatch.setattr("models.wc_predictor.compute_wc_h2h", lambda *a, **k: MagicMock(total=0, home_wins=0, draws=0, away_wins=0, last_results=[]))
    monkeypatch.setattr("models.wc_predictor.group_pressure_from_features", lambda f: 0.0)
    monkeypatch.setattr("models.wc_predictor._wc_draw_rates", lambda *a, **k: (0.2, 0.2))
    monkeypatch.setattr("models.wc_predictor.draw_features_to_vector", lambda *a, **k: [])
    monkeypatch.setattr("models.wc_predictor.apply_two_stage_probs", lambda p, d, **k: p)
    monkeypatch.setattr("models.wc_predictor.apply_sofascore_nudge", lambda p, *a, **k: (p, None))
    monkeypatch.setattr("models.wc_predictor.blend_with_baseline", lambda ph, pd, pa, *a, **k: (ph, pd, pa, None))
    monkeypatch.setattr("models.wc_predictor.collision_predict", lambda *a, **k: None)
    monkeypatch.setattr("models.wc_predictor.goal_model_factors", lambda *a, **k: MagicMock(as_dict=lambda: {}))
    monkeypatch.setattr("models.wc_predictor.simulate_match_mc", lambda *a, **k: MagicMock(to_dict=lambda: {}))
    monkeypatch.setattr("models.wc_predictor.sofascore_breakdown", lambda *a, **k: {})
    monkeypatch.setattr("models.wc_predictor._build_context", lambda *a, **k: "ctx")
    monkeypatch.setattr("models.wc_predictor.get_wc_hyperparams", lambda: MagicMock(draw_prob_floor=0.18, draw_model_blend=0.5, kxl_blend_weight=0.2))
    monkeypatch.setattr("models.wc_predictor.normalize_national_team", lambda t: t)

    result = predictor.predict("Brasil", "Alemanha", phase="group", season=2026)

    assert blend_calls == [(0.5, 0.5)]
    assert result.prob_home == pytest.approx(0.6)
    assert result.model_breakdown["ensemble_weights"]["dixon_coles"] == 1.0
    assert result.model_breakdown["model_selection"]["selected_model"] == "poisson"
