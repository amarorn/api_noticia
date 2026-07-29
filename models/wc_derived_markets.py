"""Mercados derivados de 1X2, escanteios e árbitro (dupla chance, DNB, faltas, etc.)."""
from __future__ import annotations

from typing import Any

from models.poisson_corners import _poisson_prob


def double_chance_probs(p_home: float, p_draw: float, p_away: float) -> dict[str, float]:
    """Dupla chance a partir de probabilidades 1X2."""
    return {
        "1X": float(p_home + p_draw),
        "X2": float(p_draw + p_away),
        "12": float(p_home + p_away),
    }


def draw_no_bet_probs(p_home: float, p_draw: float, p_away: float) -> dict[str, float]:
    """Empate anula aposta — probabilidade condicional sem empate."""
    no_draw = max(1e-6, 1.0 - float(p_draw))
    return {
        "home": float(p_home / no_draw),
        "away": float(p_away / no_draw),
    }


def period_h2h_probs(inplay: dict[str, Any], period: str = "ft") -> tuple[float, float, float]:
    """Retorna (P1, PX, P2) para FT, 1T ou 2T."""
    if period == "1h":
        return (
            float(inplay.get("prob_ht_home") or 0),
            float(inplay.get("prob_ht_draw") or 0),
            float(inplay.get("prob_ht_away") or 0),
        )
    if period == "2h":
        return (
            float(inplay.get("prob_sh_home") or 0),
            float(inplay.get("prob_sh_draw") or 0),
            float(inplay.get("prob_sh_away") or 0),
        )
    return (
        float(inplay.get("prob_final_home") or 0),
        float(inplay.get("prob_final_draw") or 0),
        float(inplay.get("prob_final_away") or 0),
    )


def enrich_inplay_derived_probs(inplay: dict[str, Any]) -> dict[str, Any]:
    """Preenche double_chance_probs e draw_no_bet_probs por período no dict in-play."""
    out: dict[str, Any] = {}
    for period in ("ft", "1h", "2h"):
        p1, px, p2 = period_h2h_probs(inplay, period)
        if p1 + px + p2 <= 0:
            continue
        out[f"{period}_double_chance"] = double_chance_probs(p1, px, p2)
        out[f"{period}_draw_no_bet"] = draw_no_bet_probs(p1, px, p2)
    return out


def foul_line_probs(foul_lambda: float, lines: tuple[float, ...]) -> dict[str, float]:
    """Over/under de faltas totais (Poisson FT, sem contagem ao vivo)."""
    from scipy import stats as scipy_stats

    lam = max(0.5, float(foul_lambda))
    probs: dict[str, float] = {}
    for line in lines:
        threshold = int(line)
        over = 1.0 - float(scipy_stats.poisson.cdf(threshold, lam))
        key = f"over_{str(line).replace('.', '_')}"
        probs[key] = round(min(1.0, max(0.0, over)), 4)
        probs[f"under_{str(line).replace('.', '_')}"] = round(1.0 - probs[key], 4)
    return probs


def _team_over_prob(lam_ft: float, observed: int, line: float) -> float:
    """P(total time > line) com Poisson no restante + observado."""
    remaining = max(0.05, lam_ft - observed)
    threshold = int(line)
    if observed > threshold:
        return 1.0
    need = threshold - observed + 1
    p = 0.0
    for k in range(need, 32):
        p += _poisson_prob(k, remaining)
    return min(1.0, max(0.0, p))


def team_corner_line_probs(
    *,
    lambda_home_ft: float,
    lambda_away_ft: float,
    observed_home: int = 0,
    observed_away: int = 0,
    home_lines: tuple[float, ...] = (),
    away_lines: tuple[float, ...] = (),
) -> dict[str, float]:
    """Probabilidades over/under de escanteios por time (FT)."""
    probs: dict[str, float] = {}
    for line in home_lines:
        over = _team_over_prob(lambda_home_ft, observed_home, line)
        key = f"home_over_{str(line).replace('.', '_')}"
        probs[key] = round(over, 4)
        probs[f"home_under_{str(line).replace('.', '_')}"] = round(1.0 - over, 4)
    for line in away_lines:
        over = _team_over_prob(lambda_away_ft, observed_away, line)
        key = f"away_over_{str(line).replace('.', '_')}"
        probs[key] = round(over, 4)
        probs[f"away_under_{str(line).replace('.', '_')}"] = round(1.0 - over, 4)
    return probs


def corners_h2h_probs(inplay: dict[str, Any]) -> dict[str, float] | None:
    """Quem tem mais escanteios (1 / X / 2) a partir da projeção de cantos."""
    proj = inplay.get("corners_projection") or {}
    p_home = proj.get("prob_home_more_corners")
    p_draw = proj.get("prob_draw_corners")
    p_away = proj.get("prob_away_more_corners")
    if p_home is None or p_away is None:
        return None
    if p_draw is None:
        p_draw = max(0.0, 1.0 - float(p_home) - float(p_away))
    return {
        "1": round(float(p_home), 4),
        "X": round(float(p_draw), 4),
        "2": round(float(p_away), 4),
    }


def referee_foul_lambda_from_context(match_context: dict[str, Any] | None) -> float | None:
    """λ de faltas a partir do contexto (árbitro ou baseline)."""
    if not match_context:
        return None
    raw = match_context.get("referee_foul_lambda")
    if raw is not None:
        return float(raw)
    from models.wc_referee_inplay import parse_referee_from_match_context, referee_foul_lambda_adjusted

    profile = parse_referee_from_match_context(match_context)
    if profile:
        return referee_foul_lambda_adjusted(profile)
    return None
