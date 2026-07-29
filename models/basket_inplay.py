"""Modelo in-play dedicado para basquete (NBA, 48 min).

Usa prior calibrado pelo mercado (moneyline + spread + total) e simula o restante
do jogo via distribuição normal de pontos por minuto. Inclui Bayesian update da
taxa de pontos com base no placar observado e ajustes de clutch/lead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

from config import settings

logger = structlog.get_logger(__name__)

# Deve bater com ingest/superbet/parser.py::_BASKET_QUARTER_MINUTES (feed virtual/simulado).
_BASKET_QUARTER_MINUTES = 10


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
    next_quarter_number: int | None = None
    next_quarter_projection_home: float = 0.0
    next_quarter_projection_away: float = 0.0
    team_total_probs: dict[str, float] = field(default_factory=dict)
    regulation_ml_probs: dict[str, float] = field(default_factory=dict)
    odd_even_probs: dict[str, float] = field(default_factory=dict)
    period_probs: dict[str, float] = field(default_factory=dict)

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
            "next_quarter_number": self.next_quarter_number,
            "next_quarter_projection_home": round(self.next_quarter_projection_home, 1),
            "next_quarter_projection_away": round(self.next_quarter_projection_away, 1),
            "team_total_probs": {k: round(v, 4) for k, v in self.team_total_probs.items()},
            "regulation_ml_probs": {k: round(v, 4) for k, v in self.regulation_ml_probs.items()},
            "odd_even_probs": {k: round(v, 4) for k, v in self.odd_even_probs.items()},
            "period_probs": {k: round(v, 4) for k, v in self.period_probs.items()},
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
    elif moneyline_info:
        # Deriva spread apenas do moneyline quando não há spread de mercado
        ml_implied = _implied_from_odds(moneyline_info)
        prob_home = ml_implied["1"]
        expected_spread = np.log(max(prob_home, 1e-6) / max(1 - prob_home, 1e-6)) * 4.0
        market_spread_line = expected_spread
    else:
        expected_spread = default_spread
        market_spread_line = None

    return expected_total, expected_spread, market_total_line, market_spread_line


def _posterior_rate_and_diff(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
) -> tuple[float, float, float]:
    """Taxa de pontos/min posterior (após Bayesian update + clutch/lead) e diferença
    esperada para o restante do jogo. Compartilhado entre a simulação Monte Carlo
    (horizonte = jogo inteiro) e a projeção por janela (ex.: próximo quarto).

    Retorna (rate_post, diff_remaining, remaining_minutes).
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

    # Expectativa de diferença final: -market_spread (linha é handicap aplicado ao home)
    expected_final_diff = -market_spread
    # Expectativa de diferença no restante
    diff_remaining = expected_final_diff - score_diff

    return rate_post, diff_remaining, remaining


def _estimate_remaining_expectations(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
) -> tuple[float, float, float, float]:
    """Estima média e variância dos pontos restantes (jogo inteiro) de cada time."""
    rate_post, diff_remaining, remaining = _posterior_rate_and_diff(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
    )
    total_remaining = rate_post * remaining

    mu_home_rem = (total_remaining + diff_remaining) / 2.0
    mu_away_rem = (total_remaining - diff_remaining) / 2.0

    # Variância proporcional ao ritmo e ao tempo restante
    sigma_ppm = settings.basket_sigma_ppm
    sigma_home = sigma_ppm * np.sqrt(remaining) * max(rate_post / 2.0, 0.5)
    sigma_away = sigma_ppm * np.sqrt(remaining) * max(rate_post / 2.0, 0.5)

    return mu_home_rem, mu_away_rem, sigma_home, sigma_away


def _estimate_window_points(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
    window_start_minute: float,
    window_end_minute: float,
) -> tuple[float, float]:
    """Projeta pontos esperados (home, away) apenas na janela [start, end) de minutos.

    Reusa a mesma taxa posterior (rate_post) da simulação de jogo inteiro — o total
    esperado na janela escala linearmente pelo tamanho da janela. A diferença
    esperada (home - away) assume convergência linear até a diferença final
    implícita no mercado, então a fatia da janela usa a fração do tempo restante
    que ela ocupa.
    """
    rate_post, diff_remaining, remaining = _posterior_rate_and_diff(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
    )
    if remaining <= 0:
        return 0.0, 0.0

    window_start = max(float(minute), window_start_minute)
    window_end = min(float(match_minutes), window_end_minute)
    window_len = max(0.0, window_end - window_start)
    if window_len <= 0:
        return 0.0, 0.0

    frac_start = (window_start - minute) / remaining
    frac_end = (window_end - minute) / remaining
    diff_window = diff_remaining * (frac_end - frac_start)
    total_window = rate_post * window_len

    return (total_window + diff_window) / 2.0, (total_window - diff_window) / 2.0


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


def _team_total_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    team_totals: dict[str, dict[str, dict[str, float]]] | None,
    n: int,
) -> dict[str, float]:
    if not team_totals:
        return {}
    out: dict[str, float] = {}
    for side, lines in team_totals.items():
        scores = final_h if side == "home" else final_a
        for line_str in lines:
            try:
                line_val = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line_val:g}".replace(".", "_")
            out[f"{side}_over_{lk}"] = float(np.sum(scores > line_val) / n)
            out[f"{side}_under_{lk}"] = float(np.sum(scores <= line_val) / n)
    return out


def _regulation_ml_probs(final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    """1X2 ao fim do tempo regulamentar (empate possível; sem OT explícita)."""
    margin = final_h - final_a
    return {
        "1": float(np.sum(margin > 0) / n),
        "2": float(np.sum(margin < 0) / n),
        "X": float(np.sum(margin == 0) / n),
    }


def _odd_even_probs(final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    total = final_h + final_a
    odd_count = int(np.sum(total % 2 == 1))
    even_count = n - odd_count
    return {"odd": odd_count / n, "even": even_count / n}


def _observed_quarter_map(
    basket_periods: list[dict[str, int]] | None,
    home_score: int,
    away_score: int,
    current_quarter: int,
) -> dict[int, tuple[int, int]]:
    obs: dict[int, tuple[int, int]] = {}
    if basket_periods:
        for row in basket_periods:
            num = int(row.get("num") or 0)
            if num > 0:
                obs[num] = (int(row.get("home") or 0), int(row.get("away") or 0))
    prev_h = sum(v[0] for n, v in obs.items() if n < current_quarter)
    prev_a = sum(v[1] for n, v in obs.items() if n < current_quarter)
    if current_quarter not in obs:
        obs[current_quarter] = (max(0, home_score - prev_h), max(0, away_score - prev_a))
    return obs


def _simulate_quarter_matrix(
    *,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int,
    market_total: float,
    market_spread: float,
    basket_periods: list[dict[str, int]] | None,
    n_simulations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Matriz (n_sim, n_quarters) de pontos por quarto."""
    n_quarters = max(1, round(match_minutes / _BASKET_QUARTER_MINUTES))
    home_mat = np.zeros((n_simulations, n_quarters))
    away_mat = np.zeros((n_simulations, n_quarters))
    current_quarter = min(n_quarters, int(minute // _BASKET_QUARTER_MINUTES) + 1)
    obs = _observed_quarter_map(basket_periods, home_score, away_score, current_quarter)

    rate_post, diff_remaining, remaining = _posterior_rate_and_diff(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
    )
    sigma_ppm = settings.basket_sigma_ppm

    for q in range(1, n_quarters + 1):
        idx = q - 1
        q_start = (q - 1) * _BASKET_QUARTER_MINUTES
        q_end = q * _BASKET_QUARTER_MINUTES
        if q < current_quarter:
            h, a = obs.get(q, (0, 0))
            home_mat[:, idx] = h
            away_mat[:, idx] = a
            continue

        window_start = max(float(minute), q_start)
        window_end = min(float(match_minutes), q_end)
        window_len = max(0.0, window_end - window_start)
        if window_len <= 0:
            continue

        if remaining > 0:
            frac_start = (window_start - minute) / remaining
            frac_end = (window_end - minute) / remaining
            diff_window = diff_remaining * (frac_end - frac_start)
        else:
            diff_window = 0.0
        total_window = rate_post * window_len
        mu_home = max(0.0, (total_window + diff_window) / 2.0)
        mu_away = max(0.0, (total_window - diff_window) / 2.0)
        sigma = sigma_ppm * np.sqrt(window_len) * max(rate_post / 2.0, 0.5)

        if q == current_quarter:
            cur_h, cur_a = obs.get(q, (0, 0))
            rem_len = max(0.0, window_end - max(window_start, float(minute)))
            if rem_len > 0:
                frac_rem = rem_len / window_len if window_len > 0 else 0.0
                sim_h = rng.normal(loc=mu_home * frac_rem, scale=sigma * frac_rem, size=n_simulations)
                sim_a = rng.normal(loc=mu_away * frac_rem, scale=sigma * frac_rem, size=n_simulations)
                home_mat[:, idx] = cur_h + np.maximum(sim_h, 0.0)
                away_mat[:, idx] = cur_a + np.maximum(sim_a, 0.0)
            else:
                home_mat[:, idx] = cur_h
                away_mat[:, idx] = cur_a
        else:
            sim_h = rng.normal(loc=mu_home, scale=sigma, size=n_simulations)
            sim_a = rng.normal(loc=mu_away, scale=sigma, size=n_simulations)
            home_mat[:, idx] = np.maximum(sim_h, 0.0)
            away_mat[:, idx] = np.maximum(sim_a, 0.0)

    return home_mat, away_mat


def _period_probs_from_quarters(
    home_mat: np.ndarray,
    away_mat: np.ndarray,
    period_markets: dict[str, Any] | None,
    current_quarter: int,
    n: int,
) -> dict[str, float]:
    if not period_markets:
        return {}
    out: dict[str, float] = {}
    quarters = period_markets.get("quarters") or {}

    for q_str, bucket in quarters.items():
        try:
            q_num = int(q_str)
        except ValueError:
            continue
        if q_num < current_quarter:
            continue
        if q_num < 1 or q_num > home_mat.shape[1]:
            continue
        idx = q_num - 1
        q_total = home_mat[:, idx] + away_mat[:, idx]
        q_margin = home_mat[:, idx] - away_mat[:, idx]

        for line_str, sides in (bucket.get("total") or {}).items():
            try:
                line = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line:g}".replace(".", "_")
            if "over" in sides:
                out[f"q{q_num}_over_{lk}"] = float(np.sum(q_total > line) / n)
            if "under" in sides:
                out[f"q{q_num}_under_{lk}"] = float(np.sum(q_total <= line) / n)

        for side, lines in (bucket.get("team_total") or {}).items():
            scores = home_mat[:, idx] if side == "home" else away_mat[:, idx]
            for line_str, sides in (lines or {}).items():
                try:
                    line = float(str(line_str).replace(",", "."))
                except ValueError:
                    continue
                lk = f"{line:g}".replace(".", "_")
                if "over" in sides:
                    out[f"q{q_num}_{side}_over_{lk}"] = float(np.sum(scores > line) / n)
                if "under" in sides:
                    out[f"q{q_num}_{side}_under_{lk}"] = float(np.sum(scores <= line) / n)

        for key, odd_side in (bucket.get("moneyline") or {}).items():
            if not odd_side:
                continue
            if key == "1":
                out[f"q{q_num}_ml_1"] = float(np.sum(q_margin > 0) / n)
            elif key == "2":
                out[f"q{q_num}_ml_2"] = float(np.sum(q_margin < 0) / n)
            elif key == "X":
                out[f"q{q_num}_ml_X"] = float(np.sum(q_margin == 0) / n)

        for line_key, sides in (bucket.get("spread") or {}).items():
            try:
                line_val = float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
            except ValueError:
                continue
            if "home" in sides:
                out[f"q{q_num}_home_{line_key}"] = float(np.sum(q_margin + line_val > 0) / n)
            if "away" in sides:
                out[f"q{q_num}_away_{line_key}"] = float(np.sum((-q_margin) + line_val > 0) / n)

    return out


def simulate_basket_inplay(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    match_minutes: int = 40,
    moneyline_odds: dict[str, float] | None = None,
    spread_odds: dict[str, dict[str, float]] | None = None,
    total_points_odds: dict[str, dict[str, float]] | None = None,
    team_totals: dict[str, dict[str, dict[str, float]]] | None = None,
    period_markets: dict[str, Any] | None = None,
    basket_periods: list[dict[str, int]] | None = None,
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
    ttp = _team_total_probs(final_h, final_a, team_totals, n)
    reg_probs = _regulation_ml_probs(final_h, final_a, n)
    oe_probs = _odd_even_probs(final_h, final_a, n)

    rng = np.random.default_rng(seed + 1)
    home_mat, away_mat = _simulate_quarter_matrix(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
        basket_periods=basket_periods,
        n_simulations=n,
        rng=rng,
    )
    current_quarter = min(
        max(1, round(match_minutes / _BASKET_QUARTER_MINUTES)),
        int(minute // _BASKET_QUARTER_MINUTES) + 1,
    )
    pp = _period_probs_from_quarters(
        home_mat, away_mat, period_markets, current_quarter, n
    )

    ppm_home_prior = (market_total + market_spread) / (2.0 * match_minutes)
    ppm_away_prior = (market_total - market_spread) / (2.0 * match_minutes)

    total_quarters = max(1, round(match_minutes / _BASKET_QUARTER_MINUTES))
    current_quarter = min(total_quarters, int(minute // _BASKET_QUARTER_MINUTES) + 1)
    next_quarter = current_quarter + 1
    next_quarter_number = next_quarter if next_quarter <= total_quarters else None
    next_q_home, next_q_away = _estimate_window_points(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        market_total=market_total,
        market_spread=market_spread,
        window_start_minute=(current_quarter) * _BASKET_QUARTER_MINUTES,
        window_end_minute=(current_quarter + 1) * _BASKET_QUARTER_MINUTES,
    )

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
        next_quarter_number=next_quarter_number,
        next_quarter_projection_home=next_q_home,
        next_quarter_projection_away=next_q_away,
        team_total_probs=ttp,
        regulation_ml_probs=reg_probs,
        odd_even_probs=oe_probs,
        period_probs=pp,
    )
