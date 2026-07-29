"""Modelo in-play dedicado para beisebol (MLB / KBO / NPB).

Prior calibrado pelo mercado (moneyline + run line + total de corridas) e simulação
do restante do jogo por distribuição de Poisson de corridas por entrada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    team_total_probs: dict[str, float]
    rpi_home: float  # runs per inning (posterior)
    rpi_away: float
    rpi_home_prior: float
    rpi_away_prior: float
    n_simulations: int
    market_total_line: float | None = None
    market_spread_line: float | None = None
    period_probs: dict[str, float] = field(default_factory=dict)
    score_adapted: bool = False
    obs_elapsed_innings: float = 0.0

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
            "team_total_probs": {k: round(v, 4) for k, v in self.team_total_probs.items()},
            "rpi_home": round(self.rpi_home, 3),
            "rpi_away": round(self.rpi_away, 3),
            "rpi_home_prior": round(self.rpi_home_prior, 3),
            "rpi_away_prior": round(self.rpi_away_prior, 3),
            "score_adapted": self.score_adapted,
            "obs_elapsed_innings": round(self.obs_elapsed_innings, 2),
            "n_simulations": self.n_simulations,
            "market_total_line": self.market_total_line,
            "market_spread_line": self.market_spread_line,
            "period_probs": {k: round(v, 4) for k, v in self.period_probs.items()},
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
        # Ignora linhas alternativas extremas no prior (ex.: over 22.5 distorce λ)
        prior_min = 5.5
        prior_max = 13.5
        for line_str, sides in total_runs_odds.items():
            try:
                line = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            if line < prior_min or line > prior_max:
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
        else:
            # Fallback: linha mais próxima do default entre todas as disponíveis
            candidates: list[float] = []
            for line_str in total_runs_odds:
                try:
                    candidates.append(float(str(line_str).replace(",", ".")))
                except ValueError:
                    continue
            if candidates:
                market_total = min(candidates, key=lambda x: abs(x - default_total))
                market_total_line = market_total

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


def _observed_rates_from_box(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    innings_observed: list[dict[str, int]] | None,
) -> tuple[float, float, float, bool]:
    """Taxa observada de runs/entrada a partir do placar (box score quando disponível)."""
    if innings_observed:
        obs = _observed_inning_map(innings_observed, home_score, away_score, inning)
        completed = [n for n in obs if n < inning]
        elapsed = max(0.5, len(completed) + 0.5)
        return home_score / elapsed, away_score / elapsed, elapsed, True

    elapsed = max(0.5, float(inning) - 0.5)
    return home_score / elapsed, away_score / elapsed, elapsed, False


def _posterior_rates(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    match_innings: int,
    market_total: float,
    market_spread: float,
    innings_observed: list[dict[str, int]] | None = None,
) -> tuple[float, float, float, bool, float]:
    """Taxas posteriores de corridas/entrada (home, away), entradas restantes e metadados."""
    remaining = _remaining_innings(inning, match_innings)
    prior_rpi_home = (market_total + market_spread) / (2.0 * match_innings)
    prior_rpi_away = (market_total - market_spread) / (2.0 * match_innings)
    prior_rpi_home = max(0.15, prior_rpi_home)
    prior_rpi_away = max(0.15, prior_rpi_away)

    obs_home, obs_away, elapsed, box_adapted = _observed_rates_from_box(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        innings_observed=innings_observed if settings.baseball_box_score_adapt else None,
    )

    prior_w = settings.baseball_prior_weight
    obs_w = elapsed
    if box_adapted:
        obs_w = elapsed * settings.baseball_box_score_weight_boost

    post_home = (prior_w * prior_rpi_home + obs_w * obs_home) / (prior_w + obs_w)
    post_away = (prior_w * prior_rpi_away + obs_w * obs_away) / (prior_w + obs_w)

    # Late-game: time atrás pressiona um pouco
    if settings.baseball_late_boost_enabled and inning >= settings.baseball_late_inning:
        lead = home_score - away_score
        if lead < 0:
            post_home *= settings.baseball_trailing_push_factor
            post_away *= settings.baseball_lead_admin_factor
        elif lead > 0:
            post_away *= settings.baseball_trailing_push_factor
            post_home *= settings.baseball_lead_admin_factor

    return max(0.05, post_home), max(0.05, post_away), remaining, box_adapted, elapsed


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
    innings_observed: list[dict[str, int]] | None = None,
) -> tuple[np.ndarray, np.ndarray, float, float, float, bool, float]:
    rng = np.random.default_rng(random_seed)
    rpi_h, rpi_a, remaining, box_adapted, elapsed = _posterior_rates(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        market_total=market_total,
        market_spread=market_spread,
        innings_observed=innings_observed,
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

    return final_h, final_a, rpi_h, rpi_a, remaining, box_adapted, elapsed


def _moneyline_probs(final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    return {
        "1": float(np.sum(final_h > final_a) / n),
        "2": float(np.sum(final_a > final_h) / n),
    }


def _line_key(line: float) -> str:
    return f"{line:g}".replace(".", "_").replace("-", "m")


def _parse_spread_line_key(line_key: str) -> float | None:
    try:
        return float(line_key.replace("p", "").replace("m", "-").replace("_", "."))
    except ValueError:
        return None


def _spread_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    spread_odds: dict[str, dict[str, float]] | None,
    default_lines: tuple[float, ...],
    n: int,
) -> dict[str, float]:
    margin = final_h - final_a
    out: dict[str, float] = {}

    if spread_odds:
        for line_key, sides in spread_odds.items():
            line_val = _parse_spread_line_key(line_key)
            if line_val is None:
                continue
            if "home" in sides:
                out[f"home_{line_key}"] = float(np.sum(margin + line_val > 0) / n)
            if "away" in sides:
                # handicap assinado do botão visitante (ex.: -4.5)
                out[f"away_{line_key}"] = float(np.sum((-margin) + line_val > 0) / n)
        return out

    for line in sorted(default_lines):
        lk = _line_key(line)
        out[f"home_{lk}"] = float(np.sum(margin + line > 0) / n)
        out[f"away_{lk}"] = float(np.sum((-margin) + line > 0) / n)
    return out


def _team_total_probs(
    final_h: np.ndarray,
    final_a: np.ndarray,
    team_totals: dict[str, dict[str, dict[str, float]]] | None,
    n: int,
) -> dict[str, float]:
    """Probabilidades over/under por time (corridas finais do mandante/visitante)."""
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


def _observed_inning_map(
    innings_observed: list[dict[str, int]] | None,
    home_score: int,
    away_score: int,
    current_inning: int,
) -> dict[int, tuple[int, int]]:
    obs: dict[int, tuple[int, int]] = {}
    if innings_observed:
        for row in innings_observed:
            num = int(row.get("num") or 0)
            if num > 0:
                obs[num] = (int(row.get("home") or 0), int(row.get("away") or 0))
    prev_h = sum(v[0] for n, v in obs.items() if n < current_inning)
    prev_a = sum(v[1] for n, v in obs.items() if n < current_inning)
    if current_inning not in obs:
        obs[current_inning] = (max(0, home_score - prev_h), max(0, away_score - prev_a))
    return obs


def _simulate_inning_matrix(
    *,
    home_score: int,
    away_score: int,
    inning: int,
    match_innings: int,
    rpi_h: float,
    rpi_a: float,
    innings_observed: list[dict[str, int]] | None,
    n_simulations: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Matriz (n_sim, 9) de corridas por entrada para mandante e visitante."""
    max_inn = match_innings
    home_mat = np.zeros((n_simulations, max_inn))
    away_mat = np.zeros((n_simulations, max_inn))
    obs = _observed_inning_map(innings_observed, home_score, away_score, inning)

    for inn in range(1, max_inn + 1):
        idx = inn - 1
        if inn < inning:
            h, a = obs.get(inn, (0, 0))
            home_mat[:, idx] = h
            away_mat[:, idx] = a
        elif inn == inning:
            cur_h, cur_a = obs.get(inn, (0, 0))
            rem_h = rng.poisson(lam=max(0.05, rpi_h * 0.5), size=n_simulations)
            rem_a = rng.poisson(lam=max(0.05, rpi_a * 0.5), size=n_simulations)
            home_mat[:, idx] = cur_h + rem_h
            away_mat[:, idx] = cur_a + rem_a
        else:
            home_mat[:, idx] = rng.poisson(lam=max(0.05, rpi_h), size=n_simulations)
            away_mat[:, idx] = rng.poisson(lam=max(0.05, rpi_a), size=n_simulations)
    return home_mat, away_mat


def _period_probs_from_matrix(
    home_mat: np.ndarray,
    away_mat: np.ndarray,
    period_markets: dict[str, Any] | None,
    n: int,
) -> dict[str, float]:
    if not period_markets:
        return {}
    out: dict[str, float] = {}
    f5 = period_markets.get("f5") or {}

    if f5.get("total"):
        f5_h = np.sum(home_mat[:, :5], axis=1)
        f5_a = np.sum(away_mat[:, :5], axis=1)
        f5_total = f5_h + f5_a
        for line_str, sides in f5["total"].items():
            if not sides:
                continue
            try:
                line = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line:g}".replace(".", "_")
            if "over" in sides:
                out[f"f5_over_{lk}"] = float(np.sum(f5_total > line) / n)
            if "under" in sides:
                out[f"f5_under_{lk}"] = float(np.sum(f5_total <= line) / n)

    if f5.get("moneyline"):
        f5_margin = np.sum(home_mat[:, :5], axis=1) - np.sum(away_mat[:, :5], axis=1)
        if "1" in f5["moneyline"]:
            out["f5_ml_1"] = float(np.sum(f5_margin > 0) / n)
        if "2" in f5["moneyline"]:
            out["f5_ml_2"] = float(np.sum(f5_margin < 0) / n)
        if "X" in f5["moneyline"]:
            out["f5_ml_X"] = float(np.sum(f5_margin == 0) / n)

    if f5.get("spread"):
        f5_margin = np.sum(home_mat[:, :5], axis=1) - np.sum(away_mat[:, :5], axis=1)
        for line_key, sides in f5["spread"].items():
            line_val = _parse_spread_line_key(line_key)
            if line_val is None:
                continue
            if "home" in sides:
                out[f"f5_home_{line_key}"] = float(np.sum(f5_margin + line_val > 0) / n)
            if "away" in sides:
                out[f"f5_away_{line_key}"] = float(np.sum((-f5_margin) + line_val > 0) / n)

    innings = period_markets.get("innings") or {}
    for inn_str, bucket in innings.items():
        try:
            inn = int(inn_str)
        except ValueError:
            continue
        if inn < 1 or inn > home_mat.shape[1]:
            continue
        idx = inn - 1
        inn_total = home_mat[:, idx] + away_mat[:, idx]
        inn_margin = home_mat[:, idx] - away_mat[:, idx]

        for line_str, sides in (bucket.get("total") or {}).items():
            try:
                line = float(str(line_str).replace(",", "."))
            except ValueError:
                continue
            lk = f"{line:g}".replace(".", "_")
            if "over" in sides:
                out[f"inning_{inn}_over_{lk}"] = float(np.sum(inn_total > line) / n)
            if "under" in sides:
                out[f"inning_{inn}_under_{lk}"] = float(np.sum(inn_total <= line) / n)

        if bucket.get("1x2"):
            if "1" in bucket["1x2"]:
                out[f"inning_{inn}_1x2_1"] = float(np.sum(inn_margin > 0) / n)
            if "2" in bucket["1x2"]:
                out[f"inning_{inn}_1x2_2"] = float(np.sum(inn_margin < 0) / n)
            if "X" in bucket["1x2"]:
                out[f"inning_{inn}_1x2_X"] = float(np.sum(inn_margin == 0) / n)

    highest = period_markets.get("highest_inning") or {}
    if highest:
        combined = home_mat + away_mat
        max_runs = np.max(combined, axis=1, keepdims=True)
        tie_count = np.maximum(1, np.sum(combined == max_runs, axis=1))
        for inn_str in highest:
            try:
                inn = int(inn_str)
            except ValueError:
                continue
            if inn < 1 or inn > combined.shape[1]:
                continue
            is_max = combined[:, inn - 1] == max_runs[:, 0]
            out[f"highest_inning_{inn}"] = float(np.sum(is_max / tie_count) / n)

    run_n = period_markets.get("run_n") or {}
    if run_n:
        game_total = np.sum(home_mat, axis=1) + np.sum(away_mat, axis=1)
        for run_str in run_n:
            try:
                target = int(run_str)
            except ValueError:
                continue
            if "yes" in run_n[run_str]:
                out[f"run_{target}_yes"] = float(np.sum(game_total >= target) / n)
            if "no" in run_n[run_str]:
                out[f"run_{target}_no"] = float(np.sum(game_total < target) / n)

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
    team_totals: dict[str, dict[str, dict[str, float]]] | None = None,
    period_markets: dict[str, Any] | None = None,
    innings_observed: list[dict[str, int]] | None = None,
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

    final_h, final_a, rpi_h, rpi_a, remaining, score_adapted, obs_elapsed = _simulate_remaining(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        market_total=market_total,
        market_spread=market_spread,
        n_simulations=n,
        random_seed=seed,
        innings_observed=innings_observed,
    )

    ml = _moneyline_probs(final_h, final_a, n)
    sp = _spread_probs(final_h, final_a, spread_odds, settings.baseball_spread_lines, n)
    tp = _total_probs(final_h, final_a, total_runs_odds, settings.baseball_total_lines, n)
    ttp = _team_total_probs(final_h, final_a, team_totals, n)

    rng = np.random.default_rng(seed + 1)
    home_mat, away_mat = _simulate_inning_matrix(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=match_innings,
        rpi_h=rpi_h,
        rpi_a=rpi_a,
        innings_observed=innings_observed,
        n_simulations=n,
        rng=rng,
    )
    pp = _period_probs_from_matrix(home_mat, away_mat, period_markets, n)

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
        team_total_probs=ttp,
        rpi_home=rpi_h,
        rpi_away=rpi_a,
        rpi_home_prior=prior_rpi_home,
        rpi_away_prior=prior_rpi_away,
        score_adapted=score_adapted,
        obs_elapsed_innings=obs_elapsed,
        n_simulations=n,
        market_total_line=market_total_line,
        market_spread_line=market_spread_line,
        period_probs=pp,
    )
