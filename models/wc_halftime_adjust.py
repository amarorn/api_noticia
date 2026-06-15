"""Recalibração do 2T com stats congeladas do 1T (gols, escanteios, cartões)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from config import settings
from ingest.superbet.halftime_snapshot import HalftimeFrozenStats
from models.poisson_corners import DEFAULT_LINES, _poisson_prob, predict_corners


@dataclass
class GoalHalfAdjustResult:
    home_2h_factor: float
    away_2h_factor: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home_2h_factor": round(self.home_2h_factor, 4),
            "away_2h_factor": round(self.away_2h_factor, 4),
            "reasons": self.reasons,
        }


@dataclass
class HalftimeAdjustReport:
    applied: bool
    frozen_stats: dict[str, Any]
    goal_adjustment: dict[str, Any]
    corners: dict[str, Any]
    cards: dict[str, Any]
    corner_line_probs: dict[str, float] = field(default_factory=dict)
    card_line_probs: dict[str, float] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "frozen_stats": self.frozen_stats,
            "goal_adjustment": self.goal_adjustment,
            "corners": self.corners,
            "cards": self.cards,
            "corner_line_probs": {k: round(v, 4) for k, v in self.corner_line_probs.items()},
            "card_line_probs": {k: round(v, 4) for k, v in self.card_line_probs.items()},
            "summary": self.summary,
        }


def _clamp_factor(value: float, lo: float = 0.85, hi: float = 1.15) -> float:
    return float(np.clip(value, lo, hi))


def adjust_second_half_goal_lambdas(
    *,
    lambda_full_home: float,
    lambda_full_away: float,
    stats: HalftimeFrozenStats,
    corner_lambda_home: float | None = None,
    corner_lambda_away: float | None = None,
) -> GoalHalfAdjustResult:
    """Fatores multiplicativos em λ_2h com base no comportamento do 1T."""
    home_f = 1.0
    away_f = 1.0
    reasons: list[str] = []

    total_corners = stats.home_corners_1h + stats.away_corners_1h
    total_goals_ht = stats.ht_home_score + stats.ht_away_score

    if total_corners >= 5 and total_goals_ht == 0:
        if stats.home_corners_1h >= stats.away_corners_1h:
            home_f *= 1.08
            reasons.append("Pressão 1T (escanteios) sem gol — leve boost mandante")
        if stats.away_corners_1h > stats.home_corners_1h:
            away_f *= 1.08
            reasons.append("Pressão 1T (escanteios) sem gol — leve boost visitante")

    if stats.home_yellows_1h >= 2 and stats.away_yellows_1h == 0:
        home_f *= 1.04
        reasons.append("Mandante agressivo no 1T (2+ amarelos) — micro boost ofensivo")
    if stats.away_yellows_1h >= 2 and stats.home_yellows_1h == 0:
        away_f *= 1.04
        reasons.append("Visitante agressivo no 1T (2+ amarelos) — micro boost ofensivo")

    if corner_lambda_home and corner_lambda_away:
        expected_1h_home = corner_lambda_home * 0.5
        expected_1h_away = corner_lambda_away * 0.5
        if expected_1h_home > 0.5:
            rate_h = stats.home_corners_1h / expected_1h_home
            home_f *= _clamp_factor(0.92 + 0.08 * min(rate_h, 1.5))
        if expected_1h_away > 0.5:
            rate_a = stats.away_corners_1h / expected_1h_away
            away_f *= _clamp_factor(0.92 + 0.08 * min(rate_a, 1.5))

    return GoalHalfAdjustResult(
        home_2h_factor=_clamp_factor(home_f),
        away_2h_factor=_clamp_factor(away_f),
        reasons=reasons or ["Sem ajuste forte — 1T próximo do prior"],
    )


def _line_key(line: float, prefix: str) -> str:
    return f"{prefix}_{str(line).replace('.', '_')}"


def _over_under_probs_from_total(total_lam: float, observed: int, lines: tuple[float, ...]) -> dict[str, float]:
    probs: dict[str, float] = {}
    for line in lines:
        over = 0.0
        for k in range(observed, 40):
            if k + 0.5 > line:
                over += _poisson_prob(k, total_lam)
        over = min(1.0, max(0.0, over))
        key = _line_key(line, "over")
        probs[key] = round(over, 4)
        probs[_line_key(line, "under")] = round(1.0 - over, 4)
    return probs


def project_halftime_corners(
    stats: HalftimeFrozenStats,
    *,
    lambda_home_ft: float,
    lambda_away_ft: float,
    lines: tuple[float, ...] = DEFAULT_LINES,
) -> dict[str, Any]:
    """Projeta escanteios restantes (2T) e totais FT condicionados ao 1T."""
    prior_1h_home = lambda_home_ft * 0.5
    prior_1h_away = lambda_away_ft * 0.5
    prior_weight = 2.0

    obs_h = stats.home_corners_1h
    obs_a = stats.away_corners_1h
    rate_h = (obs_h + prior_weight * prior_1h_home) / (1 + prior_weight)
    rate_a = (obs_a + prior_weight * prior_1h_away) / (1 + prior_weight)

    lam_2h_home = max(0.3, rate_h * (prior_1h_home / max(prior_1h_home, 0.1)) * 0.5 * 2)
    lam_2h_away = max(0.3, rate_a * (prior_1h_away / max(prior_1h_away, 0.1)) * 0.5 * 2)

    ft_home = obs_h + lam_2h_home
    ft_away = obs_a + lam_2h_away
    pred = predict_corners(ft_home, ft_away, lines=lines)

    line_probs = _over_under_probs_from_total(
        ft_home + ft_away,
        obs_h + obs_a,
        lines,
    )

    return {
        "observed_1h_home": obs_h,
        "observed_1h_away": obs_a,
        "expected_2h_home": round(lam_2h_home, 3),
        "expected_2h_away": round(lam_2h_away, 3),
        "expected_ft_home": round(ft_home, 3),
        "expected_ft_away": round(ft_away, 3),
        "expected_ft_total": round(ft_home + ft_away, 3),
        "prob_home_more_corners": round(pred.prob_home_more, 4),
        "prob_away_more_corners": round(pred.prob_away_more, 4),
        "line_probs": line_probs,
    }


def project_halftime_cards(
    stats: HalftimeFrozenStats,
    *,
    prior_lambda_ft: float = 3.8,
    lines: tuple[float, ...] = (2.5, 3.5, 4.5, 5.5),
) -> dict[str, Any]:
    """Projeta cartões amarelos FT com base no 1T observado."""
    obs_1h = stats.home_yellows_1h + stats.away_yellows_1h
    prior_1h = prior_lambda_ft * 0.5
    prior_weight = 2.0
    rate_1h = (obs_1h + prior_weight * prior_1h) / (1 + prior_weight)
    lam_2h = max(0.5, rate_1h)
    ft_total_lam = obs_1h + lam_2h

    line_probs = _over_under_probs_from_total(ft_total_lam, obs_1h, lines)

    return {
        "observed_1h_total": obs_1h,
        "observed_1h_home": stats.home_yellows_1h,
        "observed_1h_away": stats.away_yellows_1h,
        "expected_2h_total": round(lam_2h, 3),
        "expected_ft_total": round(ft_total_lam, 3),
        "line_probs": line_probs,
    }


def build_halftime_report(
    stats: HalftimeFrozenStats | None,
    *,
    lambda_full_home: float,
    lambda_full_away: float,
    corner_lambda_home: float | None = None,
    corner_lambda_away: float | None = None,
    corner_lines: tuple[float, ...] | None = None,
    card_lines: tuple[float, ...] | None = None,
) -> HalftimeAdjustReport | None:
    if stats is None or not settings.inplay_halftime_adjust:
        return None

    goal_adj = adjust_second_half_goal_lambdas(
        lambda_full_home=lambda_full_home,
        lambda_full_away=lambda_full_away,
        stats=stats,
        corner_lambda_home=corner_lambda_home,
        corner_lambda_away=corner_lambda_away,
    )

    lam_h = corner_lambda_home if corner_lambda_home is not None else lambda_full_home * 2.2
    lam_a = corner_lambda_away if corner_lambda_away is not None else lambda_full_away * 2.2
    lines_c = corner_lines or DEFAULT_LINES
    corners = project_halftime_corners(stats, lambda_home_ft=lam_h, lambda_away_ft=lam_a, lines=lines_c)
    cards = project_halftime_cards(stats, lines=card_lines or (2.5, 3.5, 4.5, 5.5))

    corner_line_probs = dict(corners.get("line_probs") or {})
    card_line_probs = dict(cards.get("line_probs") or {})

    summary_parts = [
        f"HT {stats.ht_home_score}×{stats.ht_away_score}",
        f"esc {stats.home_corners_1h}×{stats.away_corners_1h}",
        f"cart {stats.home_yellows_1h}×{stats.away_yellows_1h}",
        f"λ2T ×{goal_adj.home_2h_factor:.2f}/{goal_adj.away_2h_factor:.2f}",
        f"esc FT ~{corners['expected_ft_total']:.1f}",
    ]

    return HalftimeAdjustReport(
        applied=True,
        frozen_stats=stats.to_dict(),
        goal_adjustment=goal_adj.to_dict(),
        corners=corners,
        cards=cards,
        corner_line_probs=corner_line_probs,
        card_line_probs=card_line_probs,
        summary=" · ".join(summary_parts),
    )
