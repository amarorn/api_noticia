"""Testes para xG ao vivo agressivo."""
from __future__ import annotations

import pytest

from models.wc_inplay_xg_aggressive import (
    adjust_lambdas_from_xg_aggressive,
    should_use_aggressive_xg,
)


def test_adjust_xg_aggressive_basic():
    """xG acumulado = 1.5 aos 45' para time com λ=1.2."""
    lam_h, lam_a, meta = adjust_lambdas_from_xg_aggressive(
        1.2, 1.0,
        home_xg=1.5, away_xg=0.5,
        minute=45,
    )
    # λ_obs_home = 1.5 / 0.5 = 3.0
    # live_weight aos 45' = 0.65 * 0.5 = 0.325
    # new_home = (1-0.325)*1.2 + 0.325*3.0 = 0.81 + 0.975 = 1.785
    # Mas clamp: max = 1.2 * 1.40 = 1.68
    assert lam_h > 1.2  # aumentou
    # away_xg = 0.5, λ_obs = 0.5 / 0.5 = 1.0 (mesmo que atual)
    # Mas com peso 0.325: new_away = (1-0.325)*1.0 + 0.325*1.0 = 1.0
    assert meta is not None
    assert meta["applied"] is True
    assert meta["source"] == "live_xg_aggressive"
    assert meta["mode"] == "aggressive"


def test_adjust_xg_aggressive_no_xg():
    """Sem xG: retorna λ original."""
    lam_h, lam_a, meta = adjust_lambdas_from_xg_aggressive(
        1.2, 1.0,
        home_xg=None, away_xg=None,
        minute=45,
    )
    assert lam_h == 1.2
    assert lam_a == 1.0
    assert meta is None


def test_adjust_xg_aggressive_minute_zero():
    """Minuto 0: não aplica."""
    lam_h, lam_a, meta = adjust_lambdas_from_xg_aggressive(
        1.2, 1.0,
        home_xg=1.5, away_xg=0.5,
        minute=0,
    )
    assert lam_h == 1.2
    assert lam_a == 1.0
    assert meta is None


def test_should_use_aggressive_xg_early():
    """Minuto < 20: não ativa."""
    assert should_use_aggressive_xg(15, {"home_xg": 1.0}) is False


def test_should_use_aggressive_xg_no_xg():
    """Sem xG: não ativa."""
    assert should_use_aggressive_xg(30, {}) is False


def test_should_use_aggressive_xg_balanced():
    """Posse equilibrada (< 15% diff): não ativa."""
    stats = {"home_xg": 1.0, "home_possession_pct": 50, "away_possession_pct": 50}
    assert should_use_aggressive_xg(30, stats) is False


def test_should_use_aggressive_xg_dominant():
    """Posse dominante + xG: ativa."""
    stats = {"home_xg": 1.0, "home_possession_pct": 70, "away_possession_pct": 30}
    assert should_use_aggressive_xg(30, stats) is True


def test_adjust_xg_aggressive_clamp():
    """Garante que não excede cap."""
    # xG muito alto: λ_obs = 10 / 0.5 = 20
    lam_h, lam_a, meta = adjust_lambdas_from_xg_aggressive(
        1.0, 1.0,
        home_xg=10.0, away_xg=0.0,
        minute=45,
    )
    # Cap = 1.0 * 1.40 = 1.40
    assert lam_h <= 1.40
    assert meta["shift_home_pct"] <= 40.0
