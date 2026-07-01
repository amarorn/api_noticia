"""Testes do modelo de handicap asiático."""
from __future__ import annotations

import pytest

from models.wc_handicap import (
    calculate_handicap_ev,
    format_handicap_key,
    handicap_probs_from_samples,
    kelly_stake,
    simulate_handicap_probabilities,
)
import numpy as np


def test_handicap_simulation_symmetry():
    """P(home -1.5) + P(away +1.5) ≈ 1 (linhas de meio-gol)."""
    probs = simulate_handicap_probabilities(1.8, 1.2, rho=-0.13, n_simulations=20_000, random_seed=7)
    home_key = format_handicap_key("home", -1.5)
    away_key = format_handicap_key("away", 1.5)
    assert home_key in probs
    assert away_key in probs
    assert abs(probs[home_key] + probs[away_key] - 1.0) < 0.02


def test_handicap_ev_calculation():
    """EV = P × O - 1."""
    assert calculate_handicap_ev(0.5, 2.2) == pytest.approx(0.1)


def test_kelly_never_negative():
    """Kelly stake é 0 quando edge é negativo."""
    assert kelly_stake(0.4, 2.0, 1000) == 0.0


def test_handicap_from_samples_integer_line_push():
    """Linha inteira: soma win + push + lose = 1."""
    diff = np.array([0, 1, 2, 1, 0], dtype=int)
    home = np.array([0, 1, 2, 1, 0], dtype=int)
    away = home - diff
    probs = handicap_probs_from_samples(home, away, lines=[0.0])
    assert format_handicap_key("home", 0.0) in probs
    assert 0.0 < probs[format_handicap_key("home", 0.0)] < 1.0


def test_skellam_rho_zero():
    probs = simulate_handicap_probabilities(1.5, 1.5, rho=0.0, n_simulations=1000)
    assert len(probs) >= 10
