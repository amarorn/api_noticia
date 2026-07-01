"""Testes do blend xG Sofascore no λ pré-jogo."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from models.poisson_wc import XgCalibration, _apply_xg_calibration
from models.xg_lambda_blend import build_xg_calibration


def _stats_df() -> pd.DataFrame:
    rows = []
    for i in range(4):
        rows.append(
            {
                "home_team": "Brasil",
                "away_team": "Egito",
                "match_date": datetime(2026, 1, 10 + i, tzinfo=timezone.utc),
                "home_xg": 2.0,
                "away_xg": 0.8,
                "home_possession_pct": 62.0,
                "away_possession_pct": 38.0,
                "home_shots_on_target": 6,
                "away_shots_on_target": 2,
                "home_big_chances": 3,
                "away_big_chances": 1,
            }
        )
        rows.append(
            {
                "home_team": "Egito",
                "away_team": "Brasil",
                "match_date": datetime(2026, 2, 10 + i, tzinfo=timezone.utc),
                "home_xg": 0.7,
                "away_xg": 1.9,
                "home_possession_pct": 40.0,
                "away_possession_pct": 60.0,
                "home_shots_on_target": 2,
                "away_shots_on_target": 5,
                "home_big_chances": 1,
                "away_big_chances": 2,
            }
        )
    return pd.DataFrame(rows)


def test_build_xg_calibration_from_stats():
    xg = build_xg_calibration("Brasil", "Egito", stats_df=_stats_df())
    assert xg is not None
    assert xg.home_xg_for is not None
    assert xg.home_xg_for > 1.5
    assert xg.away_xg_for is not None


def test_apply_xg_calibration_raises_lambda(monkeypatch):
    monkeypatch.setattr("config.settings.wc_xg_lambda_blend_enabled", True)
    monkeypatch.setattr("config.settings.wc_xg_lambda_blend_weight", 0.5)
    lam_h, lam_a = _apply_xg_calibration(
        1.0,
        1.0,
        XgCalibration(home_xg_for=2.0, away_xg_for=0.5),
    )
    assert lam_h == pytest.approx(1.5)
    assert lam_a == pytest.approx(0.75)


def test_apply_xg_disabled(monkeypatch):
    monkeypatch.setattr("config.settings.wc_xg_lambda_blend_enabled", False)
    lam_h, lam_a = _apply_xg_calibration(
        1.2,
        0.9,
        XgCalibration(home_xg_for=2.0, away_xg_for=0.5),
    )
    assert lam_h == 1.2
    assert lam_a == 0.9
