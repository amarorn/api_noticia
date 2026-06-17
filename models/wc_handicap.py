"""Modelo de Handicap Asiático baseado em simulação Monte Carlo (Poisson + Dixon-Coles)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

import numpy as np

from models.wc_monte_carlo import _sample_poisson_bivariate

Side = Literal["home", "away"]

DEFAULT_HANDICAP_LINES: tuple[float, ...] = (-2.5, -1.5, -0.5, 0.0, 0.5, 1.5, 2.5)


def format_handicap_key(side: Side, line: float) -> str:
    """Chave canônica (ex.: home_-1.5, away_+1.5)."""
    if line == 0.0:
        return f"{side}_0"
    if line > 0:
        return f"{side}_+{line:g}"
    return f"{side}_{line:g}"


def _mirror_away_line(home_line: float) -> float:
    return -home_line if home_line != 0.0 else 0.0


def _cover_fraction(diff: int, line: float, side: Side) -> float:
    """Fração de stake retornada: 1 vitória, 0.5 push, 0 derrota."""
    if side == "home":
        adj = diff + line
    else:
        adj = line - diff
    if line == int(line):
        if adj > 0:
            return 1.0
        if adj == 0:
            return 0.5
        return 0.0
    return 1.0 if adj > 0 else 0.0


def handicap_probs_from_samples(
    home_goals: np.ndarray,
    away_goals: np.ndarray,
    lines: tuple[float, ...] | list[float] | None = None,
) -> dict[str, float]:
    """Probabilidade de cobertura asiática a partir de amostras de placar final."""
    lines = tuple(lines or DEFAULT_HANDICAP_LINES)
    n = len(home_goals)
    if n == 0:
        return {}
    diff = home_goals.astype(int) - away_goals.astype(int)
    out: dict[str, float] = {}
    for line in lines:
        home_fr = np.array([_cover_fraction(int(d), line, "home") for d in diff], dtype=float)
        away_line = _mirror_away_line(line)
        away_fr = np.array([_cover_fraction(int(d), away_line, "away") for d in diff], dtype=float)
        out[format_handicap_key("home", line)] = float(np.mean(home_fr))
        out[format_handicap_key("away", away_line)] = float(np.mean(away_fr))
    return out


@lru_cache(maxsize=256)
def simulate_handicap_probabilities(
    home_lambda: float,
    away_lambda: float,
    rho: float = -0.13,
    max_goals: int = 10,
    n_simulations: int = 50_000,
    random_seed: int = 42,
) -> dict[str, float]:
    """
    Simula placares via Poisson bivariada (Dixon-Coles) e calcula
    probabilidades de cobertura para linhas de handicap comuns.
    """
    lam_h = max(0.01, float(home_lambda))
    lam_a = max(0.01, float(away_lambda))
    n = int(n_simulations)
    rng = np.random.default_rng(random_seed)

    if abs(rho) < 1e-9:
        from scipy.stats import skellam

        # Distribuição exata da diferença para λ independentes (pré-jogo, ρ≈0)
        probs: dict[str, float] = {}
        max_diff = max_goals
        for line in DEFAULT_HANDICAP_LINES:
            home_cover = 0.0
            away_line = _mirror_away_line(line)
            away_cover = 0.0
            for diff in range(-max_diff, max_diff + 1):
                p = float(skellam.pmf(diff, lam_h, lam_a))
                home_cover += p * _cover_fraction(diff, line, "home")
                away_cover += p * _cover_fraction(diff, away_line, "away")
            probs[format_handicap_key("home", line)] = round(home_cover, 6)
            probs[format_handicap_key("away", away_line)] = round(away_cover, 6)
        return probs

    h, a = _sample_poisson_bivariate(lam_h, lam_a, rho, n, rng)
    h = np.clip(h, 0, max_goals)
    a = np.clip(a, 0, max_goals)
    raw = handicap_probs_from_samples(h, a)
    return {k: round(v, 6) for k, v in raw.items()}


def calculate_handicap_ev(model_prob: float, odd: float) -> float:
    """Expected Value para handicap: EV = P_modelo × ODD - 1."""
    if odd <= 1.0:
        return -1.0
    return float(model_prob) * float(odd) - 1.0


def kelly_stake(
    model_prob: float,
    odd: float,
    bankroll: float,
    fraction: float = 0.25,
) -> float:
    """Kelly fraction para handicap, com fração conservadora."""
    if odd <= 1.0:
        return 0.0
    edge = float(model_prob) - (1.0 / odd)
    if edge <= 0:
        return 0.0
    kelly = edge / (1.0 - (1.0 / odd))
    return max(0.0, float(bankroll) * kelly * fraction)


def recommendation_for_ev(ev: float, *, min_bet: float = 0.05, min_watch: float = 0.0) -> str:
    if ev >= min_bet:
        return "bet"
    if ev >= min_watch:
        return "watch"
    return "avoid"


__all__ = [
    "DEFAULT_HANDICAP_LINES",
    "calculate_handicap_ev",
    "format_handicap_key",
    "handicap_probs_from_samples",
    "kelly_stake",
    "recommendation_for_ev",
    "simulate_handicap_probabilities",
]
