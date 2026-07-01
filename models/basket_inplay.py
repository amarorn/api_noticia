"""Modelo in-play dedicado para basquete (NBA, 48 min).

Usa prior calibrado pelo mercado (moneyline + spread + total) e simula o restante
do jogo via distribuição normal de pontos por minuto. Inclui Bayesian update da
taxa de pontos com base no placar observado e ajustes de clutch/lead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from config import settings

logger = structlog.get_logger(__name__)


@dataclass
class BasketInPlayResult:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    minute: int
    match_minutes: int
    remaining_minutes: float
    expected_final_home: float
    expected_final_away: float
    expected_total: float
    prob_home_win: float
    prob_away_win: float
    moneyline_probs: dict[str, float]
    spread_probs: dict[str, float]
    total_probs: dict[str, float]
    ppm_home: float
    ppm_away: float
    ppm_home_prior: float
    ppm_away_prior: float
    n_simulations: int
    market_total_line: float | None = None
    market_spread_line: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "current_score": f"{self.home_score}x{self.away_score}",
            "minute": self.minute,
            "match_minutes": self.match_minutes,
            "remaining_minutes": round(self.remaining_minutes, 1),
            "expected_final_home": round(self.expected_final_home, 1),
            "expected_final_away": round(self.expected_final_away, 1),
            "expected_total": round(self.expected_total, 1),
            "prob_home_win": round(self.prob_home_win, 4),
            "prob_away_win": round(self.prob_away_win, 4),
            "moneyline_probs": {k: round(v, 4) for k, v in self.moneyline_probs.items()},
            "spread_probs": {k: round(v, 4) for k, v in self.spread_probs.items()},
            "total_probs": {k: round(v, 4) for k, v in self.total_probs.items()},
            "ppm_home": round(self.ppm_home, 3),
            "ppm_away": round(self.ppm_away, 3),
            "ppm_home_prior": round(self.ppm_home_prior, 3),
            "ppm_away_prior": round(self.ppm_away_prior, 3),
            "market_total_line": self.market_total_line,
            "market_spread_line": self.market_spread_line,
            "n_simulations": self.n_simulations,
        }


def _devig_implied(probs: dict[str, float]) -> dict[str, float]:
    total = sum(probs.values()) or 1.0
    return {k: v / total for k, v in probs.items()}


def _implied_from_odds(odds: dict[str, float]) -> dict[str, float]:
    raw = {k: 1.0 / max(float(v), 1.01) for k, v in odds.items()}
    return _devig_implied(raw)


def _main_total_line(total_odds: dict[str, dict[str, float]]) -> tuple[float, float] | None:
    """Retorna (linha, total esperado) da linha principal de total de pontos.

    A linha principal é aquela com menor overround.
    """
    best = None
    best_distance = float("inf")
    for line, prices in total_odds.items():
        over = prices.get("over")
        under = prices.get("under")
        if over is None or under is None:
            continue
        try:
            line_val = float(line.replace(",", "."))
        except ValueError:
            continue
        implied = _implied_from_odds({"over": over, "under": under})
        overround = abs(implied["over"] + implied["under"] - 1.0)
        if overround < best_distance:
            best_distance = overround
            prob_over = implied["over"]
            expected_total = line_val + (prob_over - 0.5) * 2.0
            best = (line_val, expected_total)
    return best


def _main_spread_line(spread_odds: dict[str, dict[str, float]]) -> tuple[str, float, dict[str, float]] | None:
    """Retorna (line_key, linha, odds) da linha principal de spread."""
    if not spread_odds:
        return None
    best = None
    best_score = float("inf")
    for line_key, prices in spread_odds.items():
        home = prices.get("home")
        away = prices.get("away")
        if home is None or away is None:
            continue
        try:
            line_val = float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
        except ValueError:
            continue
        implied = _implied_from_odds({"home": home, "away": away})
        score = abs(implied["home"] - 0.5)
        if score < best_score:
            best_score = score
            best = (line_key, line_val, prices)
    return best


def _main_moneyline(moneyline_odds: dict[str, float]) -> dict[str, float] | None:
    if "1" in moneyline_odds and "2" in moneyline_odds:
        return {"1": moneyline_odds["1"], "2": moneyline_odds["2"]}
    return None


def _estimate_market_priors(
    *,
    moneyline_odds: dict[str, float] | None,
    spread_odds: dict[str, dict[str, float]] | None,
    total_points_odds: dict[str, dict[str, float]] | None,
) -> tuple[float, float, float | None, float | None]:
    """Estima total e spread esperados a partir do mercado.

    Retorna (expected_total, expected_spread_home, market_total_line, market_spread_line).
    """
    default_total = 232.0
    default_spread = 0.0

    total_info = _main_total_line(total_points_odds or {}) if total_points_odds else None
    spread_info = _main_spread_line(spread_odds or {}) if spread_odds else None
    moneyline_info = _main_moneyline(moneyline_odds or {}) if moneyline_odds else None

    expected_total = total_info[1] if total_info else default_total
    market_total_line = total_info[0] if total_info else None

    if spread_info:
        expected_spread = spread_info[1]
        market_spread_line = expected_spread
    else:
        expected_spread = default_spread
        market_spread_line = None

    # Refina spread com moneyline se disponível
    if moneyline_info:
        ml_implied = _implied_from_odds(moneyline_info)
        prob_home = ml_implied["1"]
        # Aproximação: cada 4 pontos ≈ 0.10 de prob em torno de 50%
        implied_spread_from_ml = np.log(max(prob_home, 1e-6) / max(1 - prob_home, 1e-6)) * 4.0
        if spread_info:
            expected_spread = (expected_spread + implied_spread_from_ml) / 2.0
        else:
            expected_spread = implied_spread_from_ml
        market_spread_line = expected_spread

    return expected_total, expected_spread, market_total_line, market_spread_line


def _estimate_remaining_expectations(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
) -> tuple[float, float, float, float]:
    """Estima média e variância dos pontos restantes de cada time.

    Faz Bayesian update da taxa total de pontos (não por time) e ajusta a
    diferença esperada no restante pelo spread de mercado menos diferença atual.
    """
    remaining = max(0.0, float(match_minutes - minute))

    # Taxa total de pontos por minuto
    rate_market = market_total / match_minutes
    rate_obs = (home_score + away_score) / max(minute, 1)

    # Prior weight em minutos-equivalente
    prior_weight_min = settings.basket_prior_weight * (match_minutes / 48.0)

    if minute > 0:
        rate_post = (rate_market * prior_weight_min + rate_obs * minute) / (
            prior_weight_min + minute
        )
    else:
        rate_post = rate_market

    # Ajustes de clutch e lead aplicados sobre a taxa total
    clutch_factor = 1.0
    if settings.basket_clutch_boost_enabled and minute >= settings.basket_clutch_minute:
        clutch_factor = settings.basket_clutch_boost

    score_diff = home_score - away_score
    lead_factor = 1.0
    if score_diff != 0:
        # Time atrás força o jogo (mais pontos totais), time à frente administra
        if score_diff > 0:
            lead_factor = settings.basket_trailing_push_factor
        else:
            lead_factor = settings.basket_lead_admin_factor

    rate_post *= clutch_factor * lead_factor
    total_remaining = rate_post * remaining

    # Expectativa de diferença no restante: spread de mercado menos diferença atual
    diff_remaining = market_spread - score_diff

    mu_home_rem = (total_remaining + diff_remaining) / 2.0
    mu_away_rem = (total_remaining - diff_remaining) / 2.0

    # Variância proporcional ao ritmo e ao tempo restante
    sigma_ppm = settings.basket_sigma_ppm
    sigma_home = sigma_ppm * np.sqrt(remaining) * max(rate_post / 2.0, 0.5)
    sigma_away = sigma_ppm * np.sqrt(remaining) * max(rate_post / 2.0, 0.5)

    return mu_home_rem, mu_away_rem, sigma_home, sigma_away


def _simulate_remaining(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
    n_simulations: int,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Simula placares finais via Monte Carlo."""
    mu_home_rem, mu_away_rem, sigma_home, sigma_away = _estimate_remaining_expectations(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
    )

    rng = np.random.default_rng(random_seed)
    home_rem = rng.normal(loc=mu_home_rem, scale=sigma_home, size=n_simulations)
    away_rem = rng.normal(loc=mu_away_rem, scale=sigma_away, size=n_simulations)

    # Não permitir pontuação negativa no restante
    home_rem = np.maximum(home_rem, 0.0)
    away_rem = np.maximum(away_rem, 0.0)

    return home_score + home_rem, away_score + away_rem


def _spread_line_key(line: float) -> str:
    if line == 0.0:
        return "0"
    sign = "p" if line > 0 else "m"
    return f"{sign}{abs(line):g}".replace(".", "_")


def _moneyline_probs(final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    home_wins = np.sum(final_h > final_a)
    away_wins = np.sum(final_h < final_a)
    draws = n - home_wins - away_wins
    return {
        "1": float((home_wins + draws * 0.5) / n),
        "2": float((away_wins + draws * 0.5) / n),
    }


def _spread_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    spread_odds: dict[str, dict[str, float]] | None,
    default_lines: tuple[float, ...],
    n: int,
) -> dict[str, float]:
    """Probabilidade de cover do spread para cada linha disponível + defaults."""
    diff = final_h - final_a
    lines: set[float] = set(default_lines)
    if spread_odds:
        for key in spread_odds:
            try:
                line_val = float(key.replace("p", "").replace("m", "-").replace("_", "."))
                lines.add(line_val)
            except ValueError:
                continue
    out: dict[str, float] = {}
    for line in sorted(lines):
        lk = _spread_line_key(line)
        out[f"home_{lk}"] = float(np.sum(diff + line > 0) / n)
        out[f"away_{lk}"] = float(np.sum(-diff - line > 0) / n)
    return out


def _total_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    total_points_odds: dict[str, dict[str, float]] | None,
    default_lines: tuple[float, ...],
    n: int,
) -> dict[str, float]:
    """Probabilidade de over/under para cada linha disponível + defaults."""
    total = final_h + final_a
    lines: set[float] = set(default_lines)
    if total_points_odds:
        for line in total_points_odds:
            try:
                lines.add(float(line.replace(",", ".")))
            except ValueError:
                continue
    out: dict[str, float] = {}
    for line in sorted(lines):
        lk = f"{line:g}".replace(".", "_")
        out[f"over_{lk}"] = float(np.sum(total > line) / n)
        out[f"under_{lk}"] = float(np.sum(total <= line) / n)
    return out


def simulate_basket_inplay(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int = 48,
    moneyline_odds: dict[str, float] | None = None,
    spread_odds: dict[str, dict[str, float]] | None = None,
    total_points_odds: dict[str, dict[str, float]] | None = None,
    n_simulations: int | None = None,
    random_seed: int | None = None,
) -> BasketInPlayResult:
    """Executa simulação in-play para basquete.

    Prior vem do mercado (total/spread/moneyline). O restante do jogo é simulado por
    distribuição normal de pontos por minuto, com Bayesian update no total e ajustes
    de clutch/lead.
    """
    minute = max(0, min(minute, match_minutes))
    n = n_simulations or settings.basket_mc_simulations
    seed = (
        random_seed
        if random_seed is not None
        else hash((home_team, away_team, home_score, away_score, minute)) % (2**32)
    )

    market_total, market_spread, market_total_line, market_spread_line = _estimate_market_priors(
        moneyline_odds=moneyline_odds,
        spread_odds=spread_odds,
        total_points_odds=total_points_odds,
    )

    final_h, final_a = _simulate_remaining(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
        n_simulations=n,
        random_seed=seed,
    )

    ml_probs = _moneyline_probs(final_h, final_a, n)
    sp_probs = _spread_probs(final_h, final_a, spread_odds, settings.basket_spread_lines, n)
    tp_probs = _total_probs(final_h, final_a, total_points_odds, settings.basket_total_lines, n)

    ppm_total = (market_total / match_minutes) if match_minutes > 0 else 0.0
    ppm_home_prior = (market_total + market_spread) / (2.0 * match_minutes)
    ppm_away_prior = (market_total - market_spread) / (2.0 * match_minutes)

    return BasketInPlayResult(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        remaining_minutes=float(match_minutes - minute),
        expected_final_home=float(np.mean(final_h)),
        expected_final_away=float(np.mean(final_a)),
        expected_total=float(np.mean(final_h + final_a)),
        prob_home_win=ml_probs["1"],
        prob_away_win=ml_probs["2"],
        moneyline_probs=ml_probs,
        spread_probs=sp_probs,
        total_probs=tp_probs,
        ppm_home=float(np.mean(final_h - home_score) / max(match_minutes - minute, 1)),
        ppm_away=float(np.mean(final_a - away_score) / max(match_minutes - minute, 1)),
        ppm_home_prior=ppm_home_prior,
        ppm_away_prior=ppm_away_prior,
        n_simulations=n,
        market_total_line=market_total_line,
        market_spread_line=market_spread_line,
    )
