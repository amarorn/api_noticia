"""Mercados in-play condicionados ao placar e minuto (Poisson + Monte Carlo)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import structlog

from config import settings
from models.wc_handicap import handicap_probs_from_samples
from models.wc_monte_carlo import _sample_poisson_bivariate
from pipelines.wc_intensity_profile import compute_half_lambdas_nhpp

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Bayesian update de λ com gols observados (P0.1)
# ---------------------------------------------------------------------------
# Conjugada Gamma-Poisson: λ ~ Gamma(α, β)
# Prior: α = λ_prior × prior_weight, β = prior_weight
# Evidência: goals observados em t minutos (fração do jogo)
# Posterior: α_post = α + goals, β_post = β + t_elapsed
# E[λ_full | goals] = α_post / β_post
#
# prior_weight controla quanto confiamos no modelo pré-jogo vs evidência:
#   - prior_weight alto (ex: 5) → modelo pré-jogo domina
#   - prior_weight baixo (ex: 2) → evidência ao vivo domina rápido
# ---------------------------------------------------------------------------

_BAYESIAN_PRIOR_WEIGHT = 5.0  # Moderado-alto: evita overreaction a 1 gol cedo


def bayesian_lambda_update(
    lambda_prior: float,
    goals_observed: int,
    minutes_elapsed: int,
    match_minutes: int = 90,
    prior_weight: float = _BAYESIAN_PRIOR_WEIGHT,
) -> float:
    """Atualiza λ_full usando posterior Gamma-Poisson.

    Retorna a expectativa posterior de λ por jogo completo (90 min).
    Se minutos = 0, retorna o prior sem alteração.
    """
    if minutes_elapsed <= 0 or match_minutes <= 0:
        return lambda_prior

    # Fração do jogo decorrida (normalizada para 1 jogo)
    t_elapsed = minutes_elapsed / match_minutes

    # Parâmetros Gamma prior
    alpha_prior = lambda_prior * prior_weight
    beta_prior = prior_weight

    # Posterior
    alpha_post = alpha_prior + goals_observed
    beta_post = beta_prior + t_elapsed

    # E[λ_full] = E[λ_por_jogo] = α_post / β_post
    lambda_posterior = alpha_post / beta_post

    # Limitar para não explodir (máx 2.5× o prior, mín 0.3× o prior)
    lower = lambda_prior * 0.3
    upper = lambda_prior * 2.5
    return float(np.clip(lambda_posterior, lower, upper))


@dataclass
class InPlayResult:
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    minute: int
    match_minutes: int
    remaining_fraction: float
    lambda_full_home: float
    lambda_full_away: float
    lambda_remaining_home: float
    lambda_remaining_away: float
    rho_used: float
    prob_final_home: float
    prob_final_draw: float
    prob_final_away: float
    prob_ht_home: float
    prob_ht_draw: float
    prob_ht_away: float
    prob_sh_home: float
    prob_sh_draw: float
    prob_sh_away: float
    prob_no_more_goals: float
    prob_next_goal_home: float
    prob_next_goal_away: float
    final_line_probs: dict[str, float]
    remainder_line_probs: dict[str, float]
    ht_line_probs: dict[str, float]
    second_half_line_probs: dict[str, float]
    team_final_line_probs: dict[str, float]
    top_final_scores: dict[str, float]
    ht_correct_scores: dict[str, float]
    sh_correct_scores: dict[str, float]
    ht_exact_totals: dict[str, float]
    sh_exact_totals: dict[str, float]
    ht_home_exact: dict[str, float]
    ht_away_exact: dict[str, float]
    sh_home_exact: dict[str, float]
    sh_away_exact: dict[str, float]
    ht_handicap_probs: dict[str, float]
    sh_handicap_probs: dict[str, float]
    top_ht_ft: dict[str, float]
    combo_markets: dict[str, float]
    btts_final: float
    handicap_probs: dict[str, float]
    n_simulations: int
    ft_handicap_probs: dict[str, float] = field(default_factory=dict)
    ft_asian_handicap_probs: dict[str, float] = field(default_factory=dict)
    ht_asian_handicap_probs: dict[str, float] = field(default_factory=dict)
    sh_asian_handicap_probs: dict[str, float] = field(default_factory=dict)
    ft_handicap_3way_probs: dict[str, float] = field(default_factory=dict)
    ht_handicap_3way_probs: dict[str, float] = field(default_factory=dict)
    sh_handicap_3way_probs: dict[str, float] = field(default_factory=dict)
    features: Any = None
    ensemble_shadow: dict[str, Any] | None = None
    halftime_adjustment: dict[str, Any] | None = None
    lambda_adjustment: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "current_score": f"{self.home_score}x{self.away_score}",
            "minute": self.minute,
            "match_minutes": self.match_minutes,
            "remaining_fraction": round(self.remaining_fraction, 4),
            "lambda_full_home": round(self.lambda_full_home, 3),
            "lambda_full_away": round(self.lambda_full_away, 3),
            "lambda_remaining_home": round(self.lambda_remaining_home, 3),
            "lambda_remaining_away": round(self.lambda_remaining_away, 3),
            "rho_used": round(self.rho_used, 4),
            "prob_final_home": round(self.prob_final_home, 4),
            "prob_final_draw": round(self.prob_final_draw, 4),
            "prob_final_away": round(self.prob_final_away, 4),
            "prob_ht_home": round(self.prob_ht_home, 4),
            "prob_ht_draw": round(self.prob_ht_draw, 4),
            "prob_ht_away": round(self.prob_ht_away, 4),
            "prob_sh_home": round(self.prob_sh_home, 4),
            "prob_sh_draw": round(self.prob_sh_draw, 4),
            "prob_sh_away": round(self.prob_sh_away, 4),
            "prob_no_more_goals": round(self.prob_no_more_goals, 4),
            "prob_next_goal_home": round(self.prob_next_goal_home, 4),
            "prob_next_goal_away": round(self.prob_next_goal_away, 4),
            "final_line_probs": {k: round(v, 4) for k, v in self.final_line_probs.items()},
            "remainder_line_probs": {k: round(v, 4) for k, v in self.remainder_line_probs.items()},
            "ht_line_probs": {k: round(v, 4) for k, v in self.ht_line_probs.items()},
            "second_half_line_probs": {k: round(v, 4) for k, v in self.second_half_line_probs.items()},
            "team_final_line_probs": {k: round(v, 4) for k, v in self.team_final_line_probs.items()},
            "top_final_scores": self.top_final_scores,
            "ht_correct_scores": self.ht_correct_scores,
            "sh_correct_scores": self.sh_correct_scores,
            "ht_exact_totals": {k: round(v, 4) for k, v in self.ht_exact_totals.items()},
            "sh_exact_totals": {k: round(v, 4) for k, v in self.sh_exact_totals.items()},
            "ht_home_exact": {k: round(v, 4) for k, v in self.ht_home_exact.items()},
            "ht_away_exact": {k: round(v, 4) for k, v in self.ht_away_exact.items()},
            "sh_home_exact": {k: round(v, 4) for k, v in self.sh_home_exact.items()},
            "sh_away_exact": {k: round(v, 4) for k, v in self.sh_away_exact.items()},
            "ht_handicap_probs": {k: round(v, 4) for k, v in self.ht_handicap_probs.items()},
            "sh_handicap_probs": {k: round(v, 4) for k, v in self.sh_handicap_probs.items()},
            "ft_handicap_probs": {k: round(v, 4) for k, v in self.ft_handicap_probs.items()},
            "ft_asian_handicap_probs": {k: round(v, 4) for k, v in self.ft_asian_handicap_probs.items()},
            "ht_asian_handicap_probs": {k: round(v, 4) for k, v in self.ht_asian_handicap_probs.items()},
            "sh_asian_handicap_probs": {k: round(v, 4) for k, v in self.sh_asian_handicap_probs.items()},
            "ft_handicap_3way_probs": {k: round(v, 4) for k, v in self.ft_handicap_3way_probs.items()},
            "ht_handicap_3way_probs": {k: round(v, 4) for k, v in self.ht_handicap_3way_probs.items()},
            "sh_handicap_3way_probs": {k: round(v, 4) for k, v in self.sh_handicap_3way_probs.items()},
            "top_ht_ft": self.top_ht_ft,
            "combo_markets": {k: round(v, 4) for k, v in self.combo_markets.items()},
            "btts_final": round(self.btts_final, 4),
            "handicap_probs": {k: round(v, 4) for k, v in self.handicap_probs.items()},
            "n_simulations": self.n_simulations,
        }
        if self.ensemble_shadow:
            payload["ensemble_shadow"] = self.ensemble_shadow
        if self.halftime_adjustment:
            payload["halftime_adjustment"] = self.halftime_adjustment
        if self.lambda_adjustment:
            payload["lambda_adjustment"] = self.lambda_adjustment
        return payload


def _ensemble_shadow_summary(poisson: "InPlayResult", ensemble: "InPlayResult") -> dict[str, Any]:
    """Métricas A/B Poisson vs stack ensemble (shadow)."""
    l1 = (
        abs(poisson.prob_final_home - ensemble.prob_final_home)
        + abs(poisson.prob_final_draw - ensemble.prob_final_draw)
        + abs(poisson.prob_final_away - ensemble.prob_final_away)
    )
    return {
        "prob_final_home": round(ensemble.prob_final_home, 4),
        "prob_final_draw": round(ensemble.prob_final_draw, 4),
        "prob_final_away": round(ensemble.prob_final_away, 4),
        "poisson_prob_final_home": round(poisson.prob_final_home, 4),
        "poisson_prob_final_draw": round(poisson.prob_final_draw, 4),
        "poisson_prob_final_away": round(poisson.prob_final_away, 4),
        "prob_l1_delta": round(l1, 4),
    }


def _team_final_lines(final_h: np.ndarray, final_a: np.ndarray) -> dict[str, float]:
    home = _line_probs_from_totals(final_h, [0.5, 1.5, 2.5, 3.5])
    away = _line_probs_from_totals(final_a, [0.5, 1.5, 2.5])
    out: dict[str, float] = {}
    for key, val in home.items():
        out[f"home_{key}"] = val
    for key, val in away.items():
        out[f"away_{key}"] = val
    return out


def _line_probs_from_totals(totals: np.ndarray, lines: list[float]) -> dict[str, float]:
    out: dict[str, float] = {}
    n = len(totals)
    for line in lines:
        key_over = f"over_{line}".replace(".", "_")
        key_under = f"under_{line}".replace(".", "_")
        out[key_over] = float(np.sum(totals > line) / n)
        out[key_under] = float(np.sum(totals <= line) / n)
    return out


def _apply_guaranteed_lines(
    line_probs: dict[str, float], current_total: int
) -> dict[str, float]:
    """P0.2: override determinístico — se o placar atual já bateu a linha,
    a prob over é 1.0 e under é 0.0 (certeza matemática)."""
    result = dict(line_probs)
    for key in list(result.keys()):
        if not key.startswith("over_"):
            continue
        # Extrai a linha: over_2_5 → 2.5
        line_str = key.replace("over_", "").replace("_", ".")
        try:
            line_val = float(line_str)
        except ValueError:
            continue
        under_key = key.replace("over_", "under_")
        if current_total > line_val:
            result[key] = 1.0
            if under_key in result:
                result[under_key] = 0.0
    return result


def _apply_team_guaranteed_lines(
    team_lines: dict[str, float],
    home_score: int,
    away_score: int,
) -> dict[str, float]:
    """P0.2: override determinístico para linhas por time (formato flat: home_over_0_5, away_over_1_5, etc.)."""
    result = dict(team_lines)
    for key in list(result.keys()):
        if key.startswith("home_over_"):
            line_str = key.replace("home_over_", "").replace("_", ".")
            try:
                line_val = float(line_str)
            except ValueError:
                continue
            under_key = key.replace("_over_", "_under_")
            if home_score > line_val:
                result[key] = 1.0
                if under_key in result:
                    result[under_key] = 0.0
        elif key.startswith("away_over_"):
            line_str = key.replace("away_over_", "").replace("_", ".")
            try:
                line_val = float(line_str)
            except ValueError:
                continue
            under_key = key.replace("_over_", "_under_")
            if away_score > line_val:
                result[key] = 1.0
                if under_key in result:
                    result[under_key] = 0.0
    return result


def _outcome(h: np.ndarray, a: np.ndarray) -> np.ndarray:
    out = np.full(len(h), "X", dtype=object)
    out[h > a] = "1"
    out[h < a] = "2"
    return out


def _half_lambdas(
    *,
    minute: int,
    match_minutes: int,
    lambda_full_home: float,
    lambda_full_away: float,
    ht_home_score: int | None,
    ht_away_score: int | None,
) -> tuple[float, float, float, float, int, int]:
    half = match_minutes // 2
    if minute <= half:
        rem_1h_min = half - minute
        lam_rem_1h_h = lambda_full_home * rem_1h_min / match_minutes
        lam_rem_1h_a = lambda_full_away * rem_1h_min / match_minutes
        lam_2h_h = lambda_full_home * half / match_minutes
        lam_2h_a = lambda_full_away * half / match_minutes
        return lam_rem_1h_h, lam_rem_1h_a, lam_2h_h, lam_2h_a, 0, 0

    ht_h = ht_home_score if ht_home_score is not None else 0
    ht_a = ht_away_score if ht_away_score is not None else 0
    rem_2h_min = match_minutes - minute
    lam_rem_1h_h = lam_rem_1h_a = 0.0
    lam_2h_h = lambda_full_home * rem_2h_min / match_minutes
    lam_2h_a = lambda_full_away * rem_2h_min / match_minutes
    return lam_rem_1h_h, lam_rem_1h_a, lam_2h_h, lam_2h_a, ht_h, ht_a


def _combo_markets(
    *,
    ht_h: np.ndarray,
    ht_a: np.ndarray,
    final_h: np.ndarray,
    final_a: np.ndarray,
    h_2h: np.ndarray,
    a_2h: np.ndarray,
    n: int,
) -> dict[str, float]:
    ht_total = ht_h + ht_a
    sh_total = h_2h + a_2h
    match_total = final_h + final_a
    btts = (final_h > 0) & (final_a > 0)
    def rate(mask: np.ndarray) -> float:
        return float(np.sum(mask) / n)

    combos = {
        "btts_and_over_2_5": rate(btts & (match_total > 2.5)),
        "btts_and_over_3_5": rate(btts & (match_total > 3.5)),
        "ft_home_and_btts": rate((final_h > final_a) & btts),
        "ft_draw_and_btts": rate((final_h == final_a) & btts),
        "ft_away_and_btts": rate((final_h < final_a) & btts),
        "ht_or_ft_home": rate((ht_h > ht_a) | (final_h > final_a)),
        "ht_or_ft_draw": rate((ht_h == ht_a) | (final_h == final_a)),
        "ht_or_ft_away": rate((ht_h < ht_a) | (final_h < final_a)),
        "home_wins_either_half": rate((ht_h > ht_a) | (h_2h > a_2h)),
        "away_wins_either_half": rate((ht_h < ht_a) | (h_2h < a_2h)),
        "ht_over_0_5_and_match_over_1_5": rate((ht_total > 0.5) & (match_total > 1.5)),
        "ht_over_0_5_and_match_over_2_5": rate((ht_total > 0.5) & (match_total > 2.5)),
        "ht_over_1_5_and_match_over_2_5": rate((ht_total > 1.5) & (match_total > 2.5)),
        "ht_over_1_5_and_match_over_3_5": rate((ht_total > 1.5) & (match_total > 3.5)),
        "ht_over_0_5_and_2h_over_0_5": rate((ht_total > 0.5) & (sh_total > 0.5)),
        "ht_over_1_5_and_2h_over_1_5": rate((ht_total > 1.5) & (sh_total > 1.5)),
        "ht_over_0_5_or_2h_over_0_5": rate((ht_total > 0.5) | (sh_total > 0.5)),
        "ht_over_1_5_or_2h_over_1_5": rate((ht_total > 1.5) | (sh_total > 1.5)),
        "ht_over_1_5_or_match_over_2_5": rate((ht_total > 1.5) | (match_total > 2.5)),
        "ht_over_0_5_or_match_over_2_5": rate((ht_total > 0.5) | (match_total > 2.5)),
    }
    return combos


def _top_ht_ft(ht_h: np.ndarray, ht_a: np.ndarray, final_h: np.ndarray, final_a: np.ndarray, n: int) -> dict[str, float]:
    ht_out = _outcome(ht_h, ht_a)
    ft_out = _outcome(final_h, final_a)
    counts: dict[str, int] = {}
    for ho, fo in zip(ht_out, ft_out, strict=False):
        key = f"{ho}/{fo}"
        counts[key] = counts.get(key, 0) + 1
    return {k: round(v / n, 4) for k, v in sorted(counts.items(), key=lambda x: -x[1])[:9]}


_HALF_HANDICAP_LINES = (-1.5, -0.5, 0.0, 0.5, 1.5)
_FT_HANDICAP_LINES = (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0)
_FT_HANDICAP_3WAY_LINES = (-2, -1, 0, 1, 2)
_HALF_HANDICAP_3WAY_LINES = (-1, 0, 1)
_ASIAN_HANDICAP_LINES = (
    -1.5, -1.25, -1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5,
)
_HALF_EXACT_MAX_GOALS = 5


def _is_quarter_line(line: float) -> bool:
    return abs(line * 4 - round(line * 4)) > 1e-9 and abs(line * 2 - round(line * 2)) > 1e-9


def _asian_line_cover(diff: np.ndarray, line: float, side: str) -> np.ndarray:
    """Probabilidade de cover asiático por simulação (array bool)."""
    adj = diff + line if side == "home" else -diff - line
    if abs(line - round(line)) < 1e-9:
        return adj > 0
    return adj > 0


def _asian_effective_cover_prob(
    diff: np.ndarray,
    line: float,
    side: str,
    n: int,
) -> float:
    """Cover efetivo asiático; linhas quarto = média das duas meias-linhas adjacentes."""
    if _is_quarter_line(line):
        low = line - 0.25
        high = line + 0.25
        p_low = float(np.sum(_asian_line_cover(diff, low, side)) / n)
        p_high = float(np.sum(_asian_line_cover(diff, high, side)) / n)
        return (p_low + p_high) / 2.0
    return float(np.sum(_asian_line_cover(diff, line, side)) / n)


def _handicap_probs(
    h: np.ndarray,
    a: np.ndarray,
    n: int,
    lines: tuple[float, ...] = _HALF_HANDICAP_LINES,
) -> dict[str, float]:
    """Handicap europeu: home_cover = P(h - a + line > 0)."""
    diff = h.astype(float) - a.astype(float)
    out: dict[str, float] = {}
    for line in lines:
        lk = _handicap_line_key(line)
        out[f"home_{lk}"] = float(np.sum(diff + line > 0) / n)
        out[f"away_{lk}"] = float(np.sum(-diff - line > 0) / n)
    return out


def _handicap_3way_probs(
    h: np.ndarray,
    a: np.ndarray,
    n: int,
    lines: tuple[int | float, ...] = _FT_HANDICAP_3WAY_LINES,
) -> dict[str, float]:
    """Handicap 3-way: vitória/empate/derrota após aplicar linha ao mandante."""
    diff = h.astype(float) - a.astype(float)
    out: dict[str, float] = {}
    for line in lines:
        lk = _handicap_line_key(float(line))
        adjusted = diff + float(line)
        out[f"home_{lk}"] = float(np.sum(adjusted > 0) / n)
        out[f"draw_{lk}"] = float(np.sum(adjusted == 0) / n)
        out[f"away_{lk}"] = float(np.sum(adjusted < 0) / n)
    return out


def _asian_handicap_probs(
    h: np.ndarray,
    a: np.ndarray,
    n: int,
    lines: tuple[float, ...] = _ASIAN_HANDICAP_LINES,
) -> dict[str, float]:
    """Handicap asiático (inclui quartos de linha)."""
    diff = h.astype(float) - a.astype(float)
    out: dict[str, float] = {}
    for line in lines:
        lk = _handicap_line_key(line)
        out[f"home_{lk}"] = _asian_effective_cover_prob(diff, line, "home", n)
        out[f"away_{lk}"] = _asian_effective_cover_prob(diff, line, "away", n)
    return out


def _handicap_line_key(line: float) -> str:
    """Formata linha de handicap para chave estável (-0.5 → m0_5, 1.5 → p1_5)."""
    if line == 0.0:
        return "0"
    sign = "p" if line > 0 else "m"
    return f"{sign}{abs(line):g}".replace(".", "_")


def _score_distribution(
    h: np.ndarray,
    a: np.ndarray,
    n: int,
    *,
    top_k: int = 12,
) -> dict[str, float]:
    """Resultado correto por período (ex.: 1x0 → 0.18)."""
    counts: dict[str, int] = {}
    for hi, ai in zip(h, a, strict=False):
        key = f"{int(hi)}x{int(ai)}"
        counts[key] = counts.get(key, 0) + 1
    return {k: round(v / n, 4) for k, v in sorted(counts.items(), key=lambda x: -x[1])[:top_k]}


def _exact_goals_distribution(
    goals: np.ndarray,
    n: int,
    *,
    max_goals: int = _HALF_EXACT_MAX_GOALS,
) -> dict[str, float]:
    """Número exato de gols (total ou por time): 0, 1, 2, …, 5+."""
    out: dict[str, float] = {}
    for g in range(max_goals + 1):
        out[str(g)] = float(np.sum(goals == g) / n)
    out[f"{max_goals}+"] = float(np.sum(goals > max_goals) / n)
    return out


def _half_market_probs(
    *,
    ht_h: np.ndarray,
    ht_a: np.ndarray,
    h_2h: np.ndarray,
    a_2h: np.ndarray,
    n: int,
) -> dict[str, dict[str, float]]:
    """Agrega mercados de 1º e 2º tempo a partir dos arrays MC."""
    ht_total = ht_h + ht_a
    sh_total = h_2h + a_2h
    return {
        "ht_correct_scores": _score_distribution(ht_h, ht_a, n),
        "sh_correct_scores": _score_distribution(h_2h, a_2h, n),
        "ht_exact_totals": _exact_goals_distribution(ht_total, n),
        "sh_exact_totals": _exact_goals_distribution(sh_total, n),
        "ht_home_exact": _exact_goals_distribution(ht_h, n),
        "ht_away_exact": _exact_goals_distribution(ht_a, n),
        "sh_home_exact": _exact_goals_distribution(h_2h, n),
        "sh_away_exact": _exact_goals_distribution(a_2h, n),
        "ht_handicap_probs": _handicap_probs(ht_h, ht_a, n),
        "sh_handicap_probs": _handicap_probs(h_2h, a_2h, n),
        "ht_handicap_3way_probs": _handicap_3way_probs(ht_h, ht_a, n, lines=_HALF_HANDICAP_3WAY_LINES),
        "sh_handicap_3way_probs": _handicap_3way_probs(h_2h, a_2h, n, lines=_HALF_HANDICAP_3WAY_LINES),
        "ht_asian_handicap_probs": _asian_handicap_probs(ht_h, ht_a, n),
        "sh_asian_handicap_probs": _asian_handicap_probs(h_2h, a_2h, n),
    }


def _has_sofascore_momentum(momentum_events: list[dict] | None) -> bool:
    if not momentum_events:
        return False
    return any(e.get("source") == "sofascore" for e in momentum_events)


def _use_score_lambda_adjust(momentum_events: list[dict] | None) -> bool:
    """Ajuste por placar: global, Sofascore ou ScoreAlarm ao vivo."""
    if settings.inplay_score_lambda_adjust:
        return True
    if settings.inplay_score_lambda_adjust_with_sofascore:
        if _has_sofascore_momentum(momentum_events):
            return True
    if settings.inplay_score_lambda_adjust_with_scorealarm:
        from models.wc_inplay_live_adjust import has_scorealarm_momentum

        if has_scorealarm_momentum(momentum_events):
            return True
    return False


def simulate_inplay(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    lambda_full_home: float,
    lambda_full_away: float,
    match_minutes: int = 90,
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    rho: float = 0.0,
    n_simulations: int | None = None,
    random_seed: int = 42,
    bayesian_update: bool = True,
    momentum_events: list[dict] | None = None,
    home_corners: int = 0,
    away_corners: int = 0,
    market_probs: tuple[float, float, float] | None = None,
    use_nhpp: bool | None = None,
    use_market_shrinkage: bool | None = None,
    use_momentum: bool | None = None,
    halftime_stats: Any | None = None,
    live_stats: dict[str, float] | None = None,
    live_timeline: list[dict[str, Any]] | None = None,
    match_context: dict[str, Any] | None = None,
    live_research: dict[str, Any] | None = None,
) -> InPlayResult:
    minute = max(0, min(minute, match_minutes))
    half = match_minutes // 2
    remaining_fraction = max(0.0, (match_minutes - minute) / match_minutes)
    n = n_simulations or settings.wc_mc_simulations
    rng = np.random.default_rng(random_seed)
    nhpp_enabled = settings.inplay_use_nhpp if use_nhpp is None else use_nhpp
    shrinkage_enabled = (
        settings.inplay_use_market_shrinkage if use_market_shrinkage is None else use_market_shrinkage
    )
    momentum_enabled = (
        settings.inplay_momentum_on_remaining if use_momentum is None else use_momentum
    )

    # --- P0.1: Bayesian update de λ com gols observados ---
    lambda_prior_home = lambda_full_home
    lambda_prior_away = lambda_full_away
    lambda_adjust_steps: list[dict[str, Any]] = []

    def _apply_step(name: str, new_home: float, new_away: float, meta: dict[str, Any] | None) -> None:
        nonlocal lambda_full_home, lambda_full_away
        if meta is None or not meta.get("applied", True):
            return
        step = {
            "step": name,
            "lambda_before_home": round(lambda_full_home, 3),
            "lambda_before_away": round(lambda_full_away, 3),
            "lambda_after_home": round(new_home, 3),
            "lambda_after_away": round(new_away, 3),
            "delta_home_pct": round((new_home / lambda_full_home - 1.0) * 100, 2) if lambda_full_home else 0.0,
            "delta_away_pct": round((new_away / lambda_full_away - 1.0) * 100, 2) if lambda_full_away else 0.0,
        }
        step.update({k: v for k, v in (meta or {}).items() if k != "applied"})
        lambda_adjust_steps.append(step)
        lambda_full_home = new_home
        lambda_full_away = new_away

    if bayesian_update and minute > 0:
        new_h = bayesian_lambda_update(
            lambda_prior=lambda_prior_home,
            goals_observed=home_score,
            minutes_elapsed=minute,
            match_minutes=match_minutes,
        )
        new_a = bayesian_lambda_update(
            lambda_prior=lambda_prior_away,
            goals_observed=away_score,
            minutes_elapsed=minute,
            match_minutes=match_minutes,
        )
        _apply_step("bayesian", new_h, new_a, {"applied": True})

    if settings.inplay_live_stats_lambda_adjust and live_stats and minute > 0:
        from models.wc_inplay_live_adjust import adjust_lambdas_from_live_stats

        new_h, new_a, live_adj = adjust_lambdas_from_live_stats(
            lambda_full_home,
            lambda_full_away,
            live_stats=live_stats,
        )
        _apply_step("live_stats", new_h, new_a, live_adj)

    # --- xG acumulado ao vivo (Sofascore/ScoreAlarm) ---
    if settings.inplay_xg_lambda_adjust and live_stats and minute > 0:
        # Decide entre modo padrão e agressivo
        use_aggressive = (
            settings.inplay_xg_aggressive_enabled
            and minute >= 20
        )
        if use_aggressive:
            from models.wc_inplay_xg_aggressive import (
                adjust_lambdas_from_xg_aggressive,
                should_use_aggressive_xg,
            )
            if should_use_aggressive_xg(minute, live_stats):
                new_h, new_a, xg_adj = adjust_lambdas_from_xg_aggressive(
                    lambda_full_home,
                    lambda_full_away,
                    home_xg=live_stats.get("home_xg"),
                    away_xg=live_stats.get("away_xg"),
                    minute=minute,
                    match_minutes=match_minutes,
                )
                _apply_step("live_xg_aggressive", new_h, new_a, xg_adj)
            else:
                # Fallback para modo padrão
                from models.wc_inplay_live_adjust import adjust_lambdas_from_xg
                new_h, new_a, xg_adj = adjust_lambdas_from_xg(
                    lambda_full_home,
                    lambda_full_away,
                    home_xg=live_stats.get("home_xg"),
                    away_xg=live_stats.get("away_xg"),
                    minute=minute,
                    match_minutes=match_minutes,
                )
                _apply_step("live_xg", new_h, new_a, xg_adj)
        else:
            from models.wc_inplay_live_adjust import adjust_lambdas_from_xg
            new_h, new_a, xg_adj = adjust_lambdas_from_xg(
                lambda_full_home,
                lambda_full_away,
                home_xg=live_stats.get("home_xg"),
                away_xg=live_stats.get("away_xg"),
                minute=minute,
                match_minutes=match_minutes,
            )
            _apply_step("live_xg", new_h, new_a, xg_adj)

    # --- KXL dinâmico ao vivo (colisões setoriais reativas) ---
    if momentum_events and minute > 0:
        from models.wc_kxl_dynamic import KXLDynamic, apply_kxl_dynamic_to_lambda
        kxl = KXLDynamic.from_match_context(match_context)
        for ev in momentum_events:
            ev_type = ev.get("event_type", "")
            team = ev.get("team", "")
            ev_minute = ev.get("minute", 0)
            detail = ev.get("detail", "")
            if ev_type in ("goal", "red_card", "yellow_card", "substitution", "injury", "penalty"):
                kxl.apply_event(
                    ev_type,
                    team=team,
                    minute=ev_minute,
                    detail=detail,
                )
        kxl_factors = kxl.compute_factors(minute=minute)
        new_h, new_a, kxl_meta = apply_kxl_dynamic_to_lambda(
            lambda_full_home,
            lambda_full_away,
            kxl_factors,
        )
        _apply_step("kxl_dynamic", new_h, new_a, kxl_meta)

    # --- P0.2: H2H historical adjustment (comeback boost + over/under calibration) ---
    if settings.inplay_h2h_adjust and match_context is not None:
        from models.wc_inplay_h2h_adjust import parse_h2h_from_context, compute_h2h_adjust, apply_h2h_adjust

        h2h_data = parse_h2h_from_context(match_context)
        if h2h_data is not None:
            h2h_adj = compute_h2h_adjust(
                h2h_data=h2h_data,
                home_team=home_team,
                away_team=away_team,
                home_score=home_score,
                away_score=away_score,
                minute=minute,
                lambda_full_home=lambda_full_home,
                lambda_full_away=lambda_full_away,
            )
            if h2h_adj.applied:
                new_h, new_a, _ = apply_h2h_adjust(
                    lambda_full_home, lambda_full_away, h2h_adj
                )
                _apply_step("h2h", new_h, new_a, {
                    "home_factor": h2h_adj.lambda_home_factor,
                    "away_factor": h2h_adj.lambda_away_factor,
                    "draw_penalty": h2h_adj.draw_penalty,
                    "reason": h2h_adj.reason,
                })

    # Favorito pré-jogo perdendo por 1 gol: limita super-reação ao placar
    if minute >= 15 and abs(home_score - away_score) == 1:
        if away_score > home_score and lambda_prior_home > lambda_prior_away * 1.12:
            lambda_full_away = min(lambda_full_away, lambda_prior_away * 1.35)
            lambda_full_home = max(lambda_full_home, lambda_prior_home * 0.85)
        elif home_score > away_score and lambda_prior_away > lambda_prior_home * 1.12:
            lambda_full_home = min(lambda_full_home, lambda_prior_home * 1.35)
            lambda_full_away = max(lambda_full_away, lambda_prior_away * 0.85)

    # Ajuste legado em λ_full (desligado globalmente; ativo com Sofascore live)
    score_diff = home_score - away_score  # positivo = casa vence
    if _use_score_lambda_adjust(momentum_events) and score_diff != 0:
        deficit_factors = {1: 0.90, 2: 0.65, 3: 0.45, 4: 0.30}
        surplus_factors = {1: 1.08, 2: 1.18, 3: 1.25, 4: 1.30}
        abs_diff = min(abs(score_diff), 4)
        if score_diff > 0:
            # Casa vencendo: casa ganha boost, fora penalizado
            lambda_full_home *= surplus_factors[abs_diff]
            lambda_full_away *= deficit_factors[abs_diff]
        else:
            # Fora vencendo: fora ganha boost, casa penalizada
            lambda_full_away *= surplus_factors[abs_diff]
            lambda_full_home *= deficit_factors[abs_diff]
        lambda_adjust_steps.append({"step": "score_diff", "abs_diff": abs_diff})

    # --- P1c: Market shrinkage (mistura λ modelo com λ implícito do mercado) ---
    if shrinkage_enabled and market_probs is not None:
        from models.wc_market_shrinkage import shrink_lambda

        mp_h, mp_d, mp_a = market_probs
        if mp_h > 0 and mp_d > 0 and mp_a > 0:
            shrink = shrink_lambda(
                lambda_model_home=lambda_full_home,
                lambda_model_away=lambda_full_away,
                market_prob_home=mp_h,
                market_prob_draw=mp_d,
                market_prob_away=mp_a,
                minute=minute,
                match_minutes=match_minutes,
            )
            lambda_full_home = shrink.lambda_shrunk_home
            lambda_full_away = shrink.lambda_shrunk_away

    # Computar λ_remaining ANTES do momentum (Fase 1a: momentum só age em λ_remaining)
    if nhpp_enabled:
        lam_rem_1h_h, lam_2h_h = compute_half_lambdas_nhpp(
            lambda_full_home, minute, match_minutes
        )
        lam_rem_1h_a, lam_2h_a = compute_half_lambdas_nhpp(
            lambda_full_away, minute, match_minutes
        )
    else:
        lam_rem_1h_h, lam_rem_1h_a, lam_2h_h, lam_2h_a, _, _ = _half_lambdas(
            minute=minute,
            match_minutes=match_minutes,
            lambda_full_home=lambda_full_home,
            lambda_full_away=lambda_full_away,
            ht_home_score=ht_home_score,
            ht_away_score=ht_away_score,
        )

    halftime_adj_dict: dict[str, Any] | None = None
    if settings.inplay_halftime_adjust and minute > half and halftime_stats is not None:
        from models.wc_halftime_adjust import adjust_second_half_goal_lambdas

        ht_goal_adj = adjust_second_half_goal_lambdas(
            lambda_full_home=lambda_full_home,
            lambda_full_away=lambda_full_away,
            stats=halftime_stats,
        )
        lam_2h_h *= ht_goal_adj.home_2h_factor
        lam_2h_a *= ht_goal_adj.away_2h_factor
        halftime_adj_dict = {**ht_goal_adj.to_dict(), "applied": True}

    lam_h = lam_rem_1h_h + lam_2h_h
    lam_a = lam_rem_1h_a + lam_2h_a

    if settings.inplay_trailing_chase_boost and live_timeline and minute > 0:
        from models.wc_inplay_live_adjust import apply_trailing_chase_boost

        lam_h, lam_a, chase = apply_trailing_chase_boost(
            lam_h,
            lam_a,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            timeline=live_timeline,
        )
        if chase:
            lambda_adjust_steps.append({"step": "trailing_chase", **chase})

    # --- P1a: Momentum aplicado sobre λ_remaining (não λ_full) ---
    if momentum_enabled and minute > 0:
        from models.wc_live_momentum import (
            MomentumContext,
            GameEvent,
            compute_momentum_calibrated,
        )

        events = []
        for ev in (momentum_events or []):
            events.append(GameEvent(
                event_type=ev.get("event_type", "unknown"),
                minute=ev.get("minute", 0),
                team=ev.get("team", "home"),
                detail=ev.get("detail", ""),
            ))
        ctx = MomentumContext(
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            match_minutes=match_minutes,
            events=events,
            home_corners=home_corners,
            away_corners=away_corners,
        )
        momentum_result = compute_momentum_calibrated(ctx)
        # Aplicar fatores do momentum apenas sobre λ_remaining
        lam_h *= momentum_result.home_factor
        lam_a *= momentum_result.away_factor
        # Redistribuir proporcionalmente entre 1H restante e 2H
        if lam_rem_1h_h + lam_2h_h > 0:
            ratio_1h_h = lam_rem_1h_h / (lam_rem_1h_h + lam_2h_h)
            lam_rem_1h_h = lam_h * ratio_1h_h
            lam_2h_h = lam_h * (1 - ratio_1h_h)
        if lam_rem_1h_a + lam_2h_a > 0:
            ratio_1h_a = lam_rem_1h_a / (lam_rem_1h_a + lam_2h_a)
            lam_rem_1h_a = lam_a * ratio_1h_a
            lam_2h_a = lam_a * (1 - ratio_1h_a)

    h_1h_add, a_1h_add = _sample_poisson_bivariate(lam_rem_1h_h, lam_rem_1h_a, rho, n, rng)
    h_2h_add, a_2h_add = _sample_poisson_bivariate(lam_2h_h, lam_2h_a, rho, n, rng)

    if minute <= half:
        ht_h = home_score + h_1h_add
        ht_a = away_score + a_1h_add
        h_2h = h_2h_add
        a_2h = a_2h_add
        final_h = ht_h + h_2h
        final_a = ht_a + a_2h
        h_rem = h_1h_add + h_2h_add
        a_rem = a_1h_add + a_2h_add
    else:
        ht_base_h = ht_home_score if ht_home_score is not None else home_score
        ht_base_a = ht_away_score if ht_away_score is not None else away_score
        ht_h_arr = np.full(n, ht_base_h, dtype=int)
        ht_a_arr = np.full(n, ht_base_a, dtype=int)
        h_2h_base = max(0, home_score - int(ht_h_arr[0]))
        a_2h_base = max(0, away_score - int(ht_a_arr[0]))
        h_2h = h_2h_base + h_2h_add
        a_2h = a_2h_base + a_2h_add
        ht_h = ht_h_arr
        ht_a = ht_a_arr
        final_h = ht_h + h_2h
        final_a = ht_a + a_2h
        h_rem = h_2h_add
        a_rem = a_2h_add

    total_final = final_h + final_a
    rem_total = h_rem + a_rem
    ht_total = ht_h + ht_a
    sh_total = h_2h + a_2h

    home_wins = int(np.sum(final_h > final_a))
    draws = int(np.sum(final_h == final_a))
    away_wins = int(np.sum(final_h < final_a))
    ht_home_wins = int(np.sum(ht_h > ht_a))
    ht_draws = int(np.sum(ht_h == ht_a))
    ht_away_wins = int(np.sum(ht_h < ht_a))
    sh_home_wins = int(np.sum(h_2h > a_2h))
    sh_draws = int(np.sum(h_2h == a_2h))
    sh_away_wins = int(np.sum(h_2h < a_2h))
    no_more = int(np.sum((h_rem == 0) & (a_rem == 0)))

    lam_sum = lam_h + lam_a
    if lam_sum > 0:
        p_any = 1.0 - (no_more / n)
        p_next_home = (lam_h / lam_sum) * p_any
        p_next_away = (lam_a / lam_sum) * p_any
    else:
        p_next_home = p_next_away = 0.0

    scores: dict[str, int] = {}
    for fh, fa in zip(final_h, final_a, strict=False):
        key = f"{int(fh)}x{int(fa)}"
        scores[key] = scores.get(key, 0) + 1
    top_final = {
        k: round(v / n, 4)
        for k, v in sorted(scores.items(), key=lambda x: -x[1])[:8]
    }

    btts = float(np.sum((final_h > 0) & (final_a > 0)) / n)
    combo = _combo_markets(
        ht_h=ht_h,
        ht_a=ht_a,
        final_h=final_h,
        final_a=final_a,
        h_2h=h_2h,
        a_2h=a_2h,
        n=n,
    )
    # --- P0.2: Override determinístico de linhas já garantidas ---
    current_total = home_score + away_score
    final_lp = _line_probs_from_totals(total_final, [1.5, 2.5, 3.5, 4.5])
    final_lp = _apply_guaranteed_lines(final_lp, current_total)

    team_lines = _team_final_lines(final_h, final_a)
    team_lines = _apply_team_guaranteed_lines(team_lines, home_score, away_score)

    ht_lp = _line_probs_from_totals(ht_total, [0.5, 1.5, 2.5])
    sh_lp = _line_probs_from_totals(sh_total, [0.5, 1.5, 2.5])
    if minute > match_minutes // 2:
        ht_current_total = int(ht_total[0])
        ht_lp = _apply_guaranteed_lines(ht_lp, ht_current_total)
        sh_current_total = int(h_2h[0]) + int(a_2h[0])
        sh_lp = _apply_guaranteed_lines(sh_lp, sh_current_total)

    half_markets = _half_market_probs(
        ht_h=ht_h,
        ht_a=ht_a,
        h_2h=h_2h,
        a_2h=a_2h,
        n=n,
    )
    ft_handicap = _handicap_probs(final_h, final_a, n, lines=_FT_HANDICAP_LINES)
    ft_handicap_3way = _handicap_3way_probs(final_h, final_a, n, lines=_FT_HANDICAP_3WAY_LINES)
    ft_asian = _asian_handicap_probs(final_h, final_a, n)
    handicap_probs = handicap_probs_from_samples(final_h, final_a)

    from models.wc_inplay_live_adjust import build_lambda_adjustment_report

    return InPlayResult(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=match_minutes,
        remaining_fraction=remaining_fraction,
        lambda_full_home=lambda_full_home,
        lambda_full_away=lambda_full_away,
        lambda_remaining_home=lam_h,
        lambda_remaining_away=lam_a,
        rho_used=rho,
        prob_final_home=home_wins / n,
        prob_final_draw=draws / n,
        prob_final_away=away_wins / n,
        prob_ht_home=ht_home_wins / n,
        prob_ht_draw=ht_draws / n,
        prob_ht_away=ht_away_wins / n,
        prob_sh_home=sh_home_wins / n,
        prob_sh_draw=sh_draws / n,
        prob_sh_away=sh_away_wins / n,
        prob_no_more_goals=no_more / n,
        prob_next_goal_home=p_next_home,
        prob_next_goal_away=p_next_away,
        final_line_probs=final_lp,
        remainder_line_probs=_line_probs_from_totals(rem_total, [0.5, 1.5, 2.5]),
        ht_line_probs=ht_lp,
        second_half_line_probs=sh_lp,
        team_final_line_probs=team_lines,
        top_final_scores=top_final,
        ht_correct_scores=half_markets["ht_correct_scores"],
        sh_correct_scores=half_markets["sh_correct_scores"],
        ht_exact_totals=half_markets["ht_exact_totals"],
        sh_exact_totals=half_markets["sh_exact_totals"],
        ht_home_exact=half_markets["ht_home_exact"],
        ht_away_exact=half_markets["ht_away_exact"],
        sh_home_exact=half_markets["sh_home_exact"],
        sh_away_exact=half_markets["sh_away_exact"],
        ht_handicap_probs=half_markets["ht_handicap_probs"],
        sh_handicap_probs=half_markets["sh_handicap_probs"],
        ft_handicap_probs=ft_handicap,
        ft_handicap_3way_probs=ft_handicap_3way,
        ft_asian_handicap_probs=ft_asian,
        ht_asian_handicap_probs=half_markets["ht_asian_handicap_probs"],
        sh_asian_handicap_probs=half_markets["sh_asian_handicap_probs"],
        ht_handicap_3way_probs=half_markets["ht_handicap_3way_probs"],
        sh_handicap_3way_probs=half_markets["sh_handicap_3way_probs"],
        top_ht_ft=_top_ht_ft(ht_h, ht_a, final_h, final_a, n),
        combo_markets=combo,
        btts_final=btts,
        handicap_probs=handicap_probs,
        n_simulations=n,
        halftime_adjustment=halftime_adj_dict,
        lambda_adjustment=build_lambda_adjustment_report(
            lambda_prior_home=lambda_prior_home,
            lambda_prior_away=lambda_prior_away,
            lambda_full_home=lambda_full_home,
            lambda_full_away=lambda_full_away,
            steps=lambda_adjust_steps,
        ),
    )

    # Log de auditoria quando λ diverge significativamente do pré-jogo
    if lambda_adjust_steps and logger.isEnabledFor(10):  # DEBUG
        logger.debug(
            "inplay_lambda_adjustments",
            home=home_team,
            away=away_team,
            minute=minute,
            score=f"{home_score}x{away_score}",
            lambda_prior_home=round(lambda_prior_home, 3),
            lambda_prior_away=round(lambda_prior_away, 3),
            lambda_full_home=round(lambda_full_home, 3),
            lambda_full_away=round(lambda_full_away, 3),
            n_steps=len(lambda_adjust_steps),
            steps=[s["step"] for s in lambda_adjust_steps],
        )


def inplay_from_predictor(
    predictor,
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    phase: str = "group",
    is_neutral: bool = True,
    match_minutes: int = 90,
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    n_simulations: int | None = None,
    use_ensemble: bool | None = None,
    momentum_events: list[dict] | None = None,
    home_corners: int = 0,
    away_corners: int = 0,
    market_probs: tuple[float, float, float] | None = None,
    halftime_stats: Any | None = None,
    live_stats: dict[str, float] | None = None,
    live_timeline: list[dict[str, Any]] | None = None,
    before_date: datetime | None = None,
    match_context: dict[str, Any] | None = None,
    live_research: dict[str, Any] | None = None,
) -> InPlayResult:
    from datetime import datetime, timezone

    from models.poisson_wc import goal_model_factors
    from pipelines.wc_stats import build_match_features

    cutoff = before_date or datetime.now(timezone.utc)
    features = build_match_features(
        predictor.fixtures,
        home_team,
        away_team,
        before_date=cutoff,
        phase=phase,
        is_neutral=is_neutral,
    )
    rho = predictor.dixon_coles.rho
    if rho is None and predictor._dc_metrics:
        rho = predictor._dc_metrics.get("rho", 0.0)

    xg_calibration = None
    if settings.wc_xg_lambda_blend_enabled:
        from models.xg_lambda_blend import build_xg_calibration

        xg_calibration = build_xg_calibration(home_team, away_team, before_date=cutoff)

    factors = goal_model_factors(
        predictor.fixtures,
        home_team,
        away_team,
        features=features,
        before_date=cutoff,
        rho=rho,
        xg_calibration=xg_calibration,
    )
    # Aplica ajustes do live research (deep research ao vivo)
    live_research_alerts: list[str] = []
    if live_research:
        from ingest.research.live_research_pulse import apply_live_research_to_lambda
        factors.lambda_home, factors.lambda_away, live_research_alerts = apply_live_research_to_lambda(
            factors.lambda_home,
            factors.lambda_away,
            live_research,
        )
    seed = hash((home_team, away_team, home_score, away_score, minute)) % (2**32)
    sim_kwargs = dict(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        lambda_full_home=factors.lambda_home,
        lambda_full_away=factors.lambda_away,
        match_minutes=match_minutes,
        ht_home_score=ht_home_score,
        ht_away_score=ht_away_score,
        rho=float(rho or 0.0),
        n_simulations=n_simulations,
        random_seed=seed,
        momentum_events=momentum_events,
        home_corners=home_corners,
        away_corners=away_corners,
        market_probs=market_probs,
        halftime_stats=halftime_stats,
        live_stats=live_stats,
        live_timeline=live_timeline,
        match_context=match_context,
    )
    effective_use_ensemble = (
        use_ensemble if use_ensemble is not None else settings.inplay_use_ensemble
    ) and minute > 0
    shadow_ab = (
        use_ensemble is None
        and settings.inplay_use_ensemble
        and settings.inplay_ensemble_shadow_mode
        and minute > 0
    )

    if effective_use_ensemble:
        result = simulate_inplay_ensemble(**sim_kwargs)
    elif shadow_ab:
        poisson = simulate_inplay(**sim_kwargs)
        try:
            ensemble = simulate_inplay_ensemble(**sim_kwargs)
            poisson.ensemble_shadow = _ensemble_shadow_summary(poisson, ensemble)
        except Exception:
            poisson.ensemble_shadow = None
        result = poisson
    else:
        result = simulate_inplay(**sim_kwargs)

    result.features = features
    return result


# ---------------------------------------------------------------------------
# Fase 3.6: Ensemble integrando Poisson + Hawkes + GBM + Market
# ---------------------------------------------------------------------------


def simulate_inplay_ensemble(
    *,
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
    minute: int,
    lambda_full_home: float,
    lambda_full_away: float,
    match_minutes: int = 90,
    ht_home_score: int | None = None,
    ht_away_score: int | None = None,
    rho: float = 0.0,
    n_simulations: int | None = None,
    random_seed: int = 42,
    bayesian_update: bool = True,
    momentum_events: list[dict] | None = None,
    home_corners: int = 0,
    away_corners: int = 0,
    market_probs: tuple[float, float, float] | None = None,
    halftime_stats: Any | None = None,
    live_stats: dict[str, float] | None = None,
    live_timeline: list[dict[str, Any]] | None = None,
    match_context: dict[str, Any] | None = None,
) -> InPlayResult:
    """simulate_inplay com blend do ensemble (Hawkes + GBM + Market).

    Chama simulate_inplay padrão (Poisson MC) e opcionalmente enriquece as
    probabilidades 1X2 com o ensemble dinâmico da Fase 3.

    Feature flags (config.py):
    - inplay_use_ensemble: habilita/desabilita o ensemble
    - inplay_ensemble_hawkes: inclui componente Hawkes
    - inplay_ensemble_gbm: inclui componente GBM
    """
    # Resultado base (Poisson Monte Carlo)
    result = simulate_inplay(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        lambda_full_home=lambda_full_home,
        lambda_full_away=lambda_full_away,
        match_minutes=match_minutes,
        ht_home_score=ht_home_score,
        ht_away_score=ht_away_score,
        rho=rho,
        n_simulations=n_simulations,
        random_seed=random_seed,
        bayesian_update=bayesian_update,
        momentum_events=momentum_events,
        home_corners=home_corners,
        away_corners=away_corners,
        market_probs=market_probs,
        halftime_stats=halftime_stats,
        live_stats=live_stats,
        live_timeline=live_timeline,
        match_context=match_context,
    )

    if not settings.inplay_use_ensemble or minute <= 0:
        return result

    # Ensemble blend
    from models.wc_inplay_ensemble import EnsembleInput, blend_ensemble

    poisson_probs = {
        "1": result.prob_final_home,
        "X": result.prob_final_draw,
        "2": result.prob_final_away,
    }

    # Hawkes (se habilitado e dados disponíveis)
    hawkes_probs = None
    hawkes_available = settings.inplay_ensemble_hawkes
    if hawkes_available:
        try:
            from models.wc_hawkes import (
                HawkesGoalEvent,
                hawkes_probs_from_simulation,
                simulate_hawkes_batch,
            )
            from pipelines.wc_inplay_hawkes_fit import load_hawkes_params

            hawkes_params = load_hawkes_params()
            # Reconstruir gols passados
            past_goals = []
            for ev in (momentum_events or []):
                if ev.get("event_type") == "goal":
                    past_goals.append(HawkesGoalEvent(
                        minute=float(ev.get("minute", 0)),
                        team=ev.get("team", "home"),
                    ))
            # Se não temos eventos detalhados, reconstruir de forma simples
            if not past_goals:
                step = max(minute / (home_score + away_score + 1), 1.0)
                for i in range(home_score):
                    past_goals.append(HawkesGoalEvent(minute=step * (i + 1), team="home"))
                for i in range(away_score):
                    past_goals.append(HawkesGoalEvent(
                        minute=step * (home_score + i + 1), team="away"
                    ))

            mu_h = result.lambda_remaining_home / max(match_minutes - minute, 1)
            mu_a = result.lambda_remaining_away / max(match_minutes - minute, 1)
            sim = simulate_hawkes_batch(
                t_now=float(minute),
                t_end=float(match_minutes),
                mu_home=mu_h,
                mu_away=mu_a,
                params=hawkes_params,
                past_goals=past_goals,
                n_simulations=min(n_simulations or 2000, 2000),
                seed=random_seed + 1,
            )
            hawkes_probs = hawkes_probs_from_simulation(sim, home_score, away_score)
        except Exception:
            hawkes_available = False

    # GBM (se habilitado e modelo treinado)
    gbm_probs = None
    gbm_available = settings.inplay_ensemble_gbm
    if gbm_available:
        try:
            from models.wc_inplay_ensemble import gbm_probs_to_1x2
            from models.wc_inplay_gbm import InPlayGBMModel

            gbm_model = InPlayGBMModel.load()
            if gbm_model.is_fitted:
                features_dict = {
                    "minute_norm": minute / match_minutes,
                    "home_score_partial": float(home_score),
                    "away_score_partial": float(away_score),
                    "goal_diff": float(home_score - away_score),
                    "remaining_fraction": result.remaining_fraction,
                    "home_lambda_remaining": result.lambda_remaining_home,
                    "away_lambda_remaining": result.lambda_remaining_away,
                    "home_red_cards": 0.0,
                    "away_red_cards": 0.0,
                    "home_corners": float(home_corners),
                    "away_corners": float(away_corners),
                    "hawkes_intensity_home": 0.0,
                    "hawkes_intensity_away": 0.0,
                    "momentum_home_factor": 1.0,
                    "momentum_away_factor": 1.0,
                }
                gbm_pred = gbm_model.predict_single(features_dict)
                gbm_probs = gbm_probs_to_1x2(
                    gbm_pred.prob_no_goal,
                    gbm_pred.prob_goal_home,
                    gbm_pred.prob_goal_away,
                    home_score,
                    away_score,
                )
                logger.debug("gbm_inplay_active", minute=minute, home=home_team, away=away_team)
            else:
                gbm_available = False
                logger.warning(
                    "gbm_inplay_not_fitted",
                    home=home_team,
                    away=away_team,
                    minute=minute,
                    artifact_path=str(settings.lake_root / "artifacts" / "inplay_gbm.pkl"),
                )
        except Exception as exc:
            gbm_available = False
            logger.warning(
                "gbm_inplay_error",
                home=home_team,
                away=away_team,
                minute=minute,
                error=str(exc),
            )

    # Market probs (se disponível)
    market_dict = None
    market_available = market_probs is not None
    if market_available and market_probs is not None:
        mp_h, mp_d, mp_a = market_probs
        total_mp = mp_h + mp_d + mp_a
        if total_mp > 0:
            market_dict = {"1": mp_h / total_mp, "X": mp_d / total_mp, "2": mp_a / total_mp}
        else:
            market_available = False

    # Blend
    ensemble_input = EnsembleInput(
        minute=float(minute),
        poisson_probs=poisson_probs,
        hawkes_probs=hawkes_probs,
        gbm_probs=gbm_probs,
        market_probs=market_dict,
        poisson_available=True,
        hawkes_available=hawkes_available and hawkes_probs is not None,
        gbm_available=gbm_available and gbm_probs is not None,
        market_available=market_available and market_dict is not None,
    )
    ensemble_result = blend_ensemble(ensemble_input)

    # Atualizar probabilidades no resultado
    result.prob_final_home = ensemble_result.probs["1"]
    result.prob_final_draw = ensemble_result.probs["X"]
    result.prob_final_away = ensemble_result.probs["2"]

    return result
