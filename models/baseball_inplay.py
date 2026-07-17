"""Modelo in-play dedicado para beisebol (MLB / KBO / NPB).

Prior calibrado pelo mercado (moneyline + run line + total de corridas) e simulação
do restante do jogo por distribuição de Poisson de corridas por entrada.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from config import settings

logger = structlog.get_logger(__name__)


@dataclass
class BaseballInPlayResult:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    inning: int
    match_innings: int
    remaining_innings: float
    expected_final_home: float
    expected_final_away: float
    expected_total: float
    prob_home_win: float
    prob_away_win: float
    moneyline_probs: dict[str, float]
    spread_probs: dict[str, float]
    total_probs: dict[str, float]
    rpi_home: float  # runs per inning (posterior)
    rpi_away: float
    rpi_home_prior: float
    rpi_away_prior: float
    n_simulations: int
    market_total_line: float | None = None
    market_spread_line: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "current_score": f"{self.home_score}x{self.away_score}",
            "inning": self.inning,
            "match_innings": self.match_innings,
            "remaining_innings": round(self.remaining_innings, 2),
            "expected_final_home": round(self.expected_final_home, 2),
            "expected_final_away": round(self.expected_final_away, 2),
            "expected_total": round(self.expected_total, 2),
            "prob_home_win": round(self.prob_home_win, 4),
            "prob_away_win": round(self.prob_away_win, 4),
            "moneyline_probs": {k: round(v, 4) for k, v in self.moneyline_probs.items()},
            "spread_probs": {k: round(v, 4) for k, v in self.spread_probs.items()},
            "total_probs": {k: round(v, 4) for k, v in self.total_probs.items()},
            "rpi_home": round(self.rpi_home, 3),
            "rpi_away": round(self.rpi_away, 3),
            "rpi_home_prior": round(self.rpi_home_prior, 3),
            "rpi_away_prior": round(self.rpi_away_prior, 3),
            "n_simulations": self.n_simulations,
            "market_total_line": self.market_total_line,
            "market_spread_line": self.market_spread_line,
        }


def _implied_prob(odd: float) -> float:
    return 1.0 / odd if odd > 1.0 else 0.0


def _normalize_two_way(p1: float, p2: float) -> tuple[float, float]:
    total = p1 + p2
    if total <= 0:
        return 0.5, 0.5
    return p1 / total, p2 / total


def _estimate_market_priors(
    *,
    moneyline_odds: dict[str, float] | None,
    spread_odds: dict[str, dict[str, float]] | None,
    total_runs_odds: dict[str, dict[str, float]] | None,
    default_total: float,
) -> tuple[float, float, float | None, float | None]:
    """Retorna (market_total, market_spread_home_minus_away, total_line, spread_line)."""
    market_total = default_total
    market_total_line: float | None = None
    if total_runs_odds:
        best_line = None
        best_balance = 1e9
        for line_str, sides in total_runs_odds.items():
            try:
                line = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            over = sides.get("over")
            under = sides.get("under")
            if over is None or under is None:
                continue
            balance = abs(_implied_prob(over) - _implied_prob(under))
            if balance < best_balance:
                best_balance = balance
                best_line = line
        if best_line is not None:
            market_total = best_line
            market_total_line = best_line

    market_spread = 0.0
    market_spread_line: float | None = None
    if spread_odds:
        # Prefere run line clássica ±1.5
        preferred = None
        for line_key, sides in spread_odds.items():
            try:
                raw = line_key.replace("p", "").replace("m", "-").replace("_", ".")
                line = float(raw)
            except ValueError:
                continue
            if "home" not in sides or "away" not in sides:
                continue
            if preferred is None or abs(abs(line) - 1.5) < abs(abs(preferred) - 1.5):
                preferred = line
                home_p, away_p = _normalize_two_way(
                    _implied_prob(sides["home"]), _implied_prob(sides["away"])
                )
                # Linha do mandante (ex. +1.5): spread esperado ≈ -linha se favorito visitante
                market_spread = -line if home_p < away_p else line
                # Melhor: spread ≈ linha do home (home cobre se home_score - away_score > -line_home)
                # Usamos a linha home como handicap do mandante.
                market_spread = line  # home handicap line; positive = underdog home
                market_spread_line = line

    if moneyline_odds and "1" in moneyline_odds and "2" in moneyline_odds:
        p_home, p_away = _normalize_two_way(
            _implied_prob(moneyline_odds["1"]),
            _implied_prob(moneyline_odds["2"]),
        )
        # Ajusta spread suave via moneyline se não houver run line
        if market_spread_line is None:
            market_spread = (p_home - p_away) * 2.0  # ~[-2, +2]

    return market_total, market_spread, market_total_line, market_spread_line


def _remaining_innings(inning: int, match_innings: int) -> float:
    """Entradas restantes (inclui fração da atual)."""
    inning = max(1, min(inning, match_innings + 3))
    if inning > match_innings:
        return 1.0  # extras: simula ao menos 1 entrada extra
    # Assume metade da entrada atual ainda a jogar + entradas futuras
    return max(0.5, (match_innings - inning) + 0.5)


def _posterior_rates(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    match_innings: int,
    market_total: float,
    market_spread: float,
) -> tuple[float, float, float]:
    """Taxas posteriores de corridas/entrada (home, away) e entradas restantes."""
    remaining = _remaining_innings(inning, match_innings)
    elapsed = max(0.5, float(inning) - 0.5)

    prior_rpi_home = (market_total + market_spread) / (2.0 * match_innings)
    prior_rpi_away = (market_total - market_spread) / (2.0 * match_innings)
    prior_rpi_home = max(0.15, prior_rpi_home)
    prior_rpi_away = max(0.15, prior_rpi_away)

    # Pseudo-contagem em entradas-equivalente
    prior_w = settings.baseball_prior_weight
    obs_home = home_score / elapsed
    obs_away = away_score / elapsed
    post_home = (prior_w * prior_rpi_home + elapsed * obs_home) / (prior_w + elapsed)
    post_away = (prior_w * prior_rpi_away + elapsed * obs_away) / (prior_w + elapsed)

    # Late-game: time atrás pressiona um pouco
    if settings.baseball_late_boost_enabled and inning >= settings.baseball_late_inning:
        lead = home_score - away_score
        if lead < 0:
            post_home *= settings.baseball_trailing_push_factor
            post_away *= settings.baseball_lead_admin_factor
        elif lead > 0:
            post_away *= settings.baseball_trailing_push_factor
            post_home *= settings.baseball_lead_admin_factor

    return max(0.05, post_home), max(0.05, post_away), remaining


def _simulate_remaining(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    match_innings: int,
    market_total: float,
    market_spread: float,
    n_simulations: int,
    random_seed: int,
) -> tuple[np.ndarray, np.ndarray, float, float]:
    rng = np.random.default_rng(random_seed)
    rpi_h, rpi_a, remaining = _posterior_rates(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        market_total=market_total,
        market_spread=market_spread,
    )
    # Poisson por entrada restante (lambda = rpi * remaining)
    rem_h = rng.poisson(lam=rpi_h * remaining, size=n_simulations).astype(float)
    rem_a = rng.poisson(lam=rpi_a * remaining, size=n_simulations).astype(float)
    final_h = home_score + rem_h
    final_a = away_score + rem_a

    # Empate após 9: simula entradas extras até decidir (máx. 3)
    tied = final_h == final_a
    if np.any(tied):
        for _ in range(3):
            if not np.any(tied):
                break
            extra_h = rng.poisson(lam=rpi_h, size=n_simulations)
            extra_a = rng.poisson(lam=rpi_a, size=n_simulations)
            final_h = np.where(tied, final_h + extra_h, final_h)
            final_a = np.where(tied, final_a + extra_a, final_a)
            tied = final_h == final_a
        # desempate residual raro
        still = final_h == final_a
        final_h = np.where(still, final_h + 1, final_h)

    return final_h, final_a, rpi_h, rpi_a


def _moneyline_probs(final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    return {
        "1": float(np.sum(final_h > final_a) / n),
        "2": float(np.sum(final_a > final_h) / n),
    }


def _line_key(line: float) -> str:
    return f"{line:g}".replace(".", "_").replace("-", "m")


def _spread_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    spread_odds: dict[str, dict[str, float]] | None,
    default_lines: tuple[float, ...],
    n: int,
) -> dict[str, float]:
    lines: set[float] = set(default_lines)
    if spread_odds:
        for lk in spread_odds:
            try:
                raw = lk.replace("p", "").replace("m", "-").replace("_", ".")
                lines.add(float(raw))
            except ValueError:
                continue
    margin = final_h - final_a
    out: dict[str, float] = {}
    for line in sorted(lines):
        lk = _line_key(line)
        # home cobre handicap `line` se margin + line > 0 (asiático sem push simplificado)
        out[f"home_{lk}"] = float(np.sum(margin + line > 0) / n)
        out[f"away_{lk}"] = float(np.sum((-margin) + (-line) > 0) / n)
        # Normaliza se ambos existem
        s = out[f"home_{lk}"] + out[f"away_{lk}"]
        if s > 0:
            out[f"home_{lk}"] /= s
            out[f"away_{lk}"] /= s
    return out


def _total_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    total_runs_odds: dict[str, dict[str, float]] | None,
    default_lines: tuple[float, ...],
    n: int,
) -> dict[str, float]:
    lines: set[float] = set(default_lines)
    if total_runs_odds:
        for line_str in total_runs_odds:
            try:
                lines.add(float(str(line_str).replace(",", ".")))
            except ValueError:
                continue
    total = final_h + final_a
    out: dict[str, float] = {}
    for line in sorted(lines):
        lk = f"{line:g}".replace(".", "_")
        out[f"over_{lk}"] = float(np.sum(total > line) / n)
        out[f"under_{lk}"] = float(np.sum(total <= line) / n)
    return out


def simulate_baseball_inplay(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    inning: int,
    match_innings: int | None = None,
    moneyline_odds: dict[str, float] | None = None,
    spread_odds: dict[str, dict[str, float]] | None = None,
    total_runs_odds: dict[str, dict[str, float]] | None = None,
    n_simulations: int | None = None,
    random_seed: int | None = None,
) -> BaseballInPlayResult:
    """Simulação Monte Carlo in-play para beisebol."""
    match_innings = match_innings or settings.baseball_match_innings
    inning = max(1, inning)
    n = n_simulations or settings.baseball_mc_simulations
    seed = (
        random_seed
        if random_seed is not None
        else hash((home_team, away_team, home_score, away_score, inning)) % (2**32)
    )

    market_total, market_spread, market_total_line, market_spread_line = _estimate_market_priors(
        moneyline_odds=moneyline_odds,
        spread_odds=spread_odds,
        total_runs_odds=total_runs_odds,
        default_total=settings.baseball_default_total,
    )

    final_h, final_a, rpi_h, rpi_a = _simulate_remaining(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        market_total=market_total,
        market_spread=market_spread,
        n_simulations=n,
        random_seed=seed,
    )

    remaining = _remaining_innings(inning, match_innings)
    ml = _moneyline_probs(final_h, final_a, n)
    sp = _spread_probs(final_h, final_a, spread_odds, settings.baseball_spread_lines, n)
    tp = _total_probs(final_h, final_a, total_runs_odds, settings.baseball_total_lines, n)

    prior_rpi_home = (market_total + market_spread) / (2.0 * match_innings)
    prior_rpi_away = (market_total - market_spread) / (2.0 * match_innings)

    return BaseballInPlayResult(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        remaining_innings=remaining,
        expected_final_home=float(np.mean(final_h)),
        expected_final_away=float(np.mean(final_a)),
        expected_total=float(np.mean(final_h + final_a)),
        prob_home_win=ml["1"],
        prob_away_win=ml["2"],
        moneyline_probs=ml,
        spread_probs=sp,
        total_probs=tp,
        rpi_home=rpi_h,
        rpi_away=rpi_a,
        rpi_home_prior=prior_rpi_home,
        rpi_away_prior=prior_rpi_away,
        n_simulations=n,
        market_total_line=market_total_line,
        market_spread_line=market_spread_line,
    )
