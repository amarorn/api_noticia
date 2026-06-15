"""Mercados do 2º tempo ainda viáveis dado o minuto e tempo restante."""

from __future__ import annotations

import re
from typing import Any

from config import settings
from models.inplay_market_period import allow_2h_suggestions, is_second_half_market
from models.inplay_leg_compatibility import is_superbet_bet_builder_market


def _categorize_2h_market(market: str) -> str:
    if market.endswith("_h2h"):
        return "1x2"
    if "_cs_" in market:
        return "correct_score"
    if "_hcap_" in market:
        return "handicap"
    if "_exact_" in market:
        return "exact_goals"
    if "_over_" in market:
        return "totals"
    return "other"


_CATEGORY_LABELS = {
    "1x2": "1X2 2T",
    "correct_score": "RC 2T",
    "handicap": "Handicap 2T",
    "exact_goals": "Gols exatos 2T",
    "totals": "Totais 2T",
    "other": "Outros 2T",
}


def _short_label(label: str, max_len: int = 42) -> str:
    clean = re.sub(r"\s+", " ", label.strip())
    if len(clean) <= max_len:
        return clean
    return f"{clean[: max_len - 1]}…"


def build_viable_2h_markets(
    market_scan: list[dict[str, Any]],
    *,
    minute: int,
    match_minutes: int = 90,
    remaining_fraction: float | None = None,
    min_model_prob: float | None = None,
    max_markets: int | None = None,
) -> dict[str, Any]:
    """Filtra mercados 2T com probabilidade relevante no tempo que resta."""
    minutes_remaining = max(0, match_minutes - minute)
    rem_frac = remaining_fraction
    if rem_frac is None and match_minutes > 0:
        rem_frac = minutes_remaining / match_minutes

    min_prob = min_model_prob if min_model_prob is not None else settings.live_2h_viable_min_prob
    cap = max_markets if max_markets is not None else settings.live_2h_viable_max_markets

    if minute <= 45:
        return {
            "available": False,
            "closed": True,
            "closed_reason": "Mercados do 2º tempo disponíveis após o intervalo.",
            "minute": minute,
            "minutes_remaining": minutes_remaining,
            "remaining_fraction": round(rem_frac or 0, 4),
            "block_2h_minute": settings.live_block_2h_minute,
            "markets": [],
            "chart": {"categories": [], "probabilities_pct": [], "ev_pct": []},
        }

    if minute > settings.live_block_2h_minute:
        return {
            "available": False,
            "closed": True,
            "closed_reason": (
                f"Pouco tempo restante (≥{settings.live_block_2h_minute}') — "
                "mercados de 2T encerrados para novas sugestões."
            ),
            "minute": minute,
            "minutes_remaining": minutes_remaining,
            "remaining_fraction": round(rem_frac or 0, 4),
            "block_2h_minute": settings.live_block_2h_minute,
            "markets": [],
            "chart": {"categories": [], "probabilities_pct": [], "ev_pct": []},
        }

    pool: list[dict[str, Any]] = []
    for row in market_scan:
        market = str(row.get("market") or "")
        if not is_second_half_market(market):
            continue
        if not is_superbet_bet_builder_market(market):
            continue
        prob = float(row.get("model_prob") or 0)
        if prob < min_prob:
            continue
        category = _categorize_2h_market(market)
        pool.append({
            "market": market,
            "outcome": str(row.get("outcome") or "yes"),
            "label": str(row.get("label") or market),
            "short_label": _short_label(str(row.get("label") or market)),
            "category": category,
            "category_label": _CATEGORY_LABELS.get(category, category),
            "model_prob": round(prob, 4),
            "market_odd": round(float(row.get("market_odd") or 0), 3),
            "implied_prob": round(float(row.get("implied_prob") or 0), 4),
            "expected_value": round(float(row.get("expected_value") or 0), 4),
            "edge_pp": round(float(row.get("edge_pp") or 0), 2),
            "meets_threshold": bool(row.get("meets_threshold")),
            "viability_score": round(prob * (1.0 + max(0.0, float(row.get("expected_value") or 0))), 4),
        })

    pool.sort(
        key=lambda r: (r["viability_score"], r["model_prob"], r["expected_value"]),
        reverse=True,
    )
    markets = pool[:cap]

    # Gráfico: melhor mercado por categoria (prob. do modelo)
    by_cat: dict[str, dict[str, Any]] = {}
    for row in pool:
        cat = row["category"]
        if cat not in by_cat or row["model_prob"] > by_cat[cat]["model_prob"]:
            by_cat[cat] = row
    chart_rows = sorted(by_cat.values(), key=lambda r: r["model_prob"], reverse=True)

    return {
        "available": bool(markets) and allow_2h_suggestions(minute),
        "closed": False,
        "closed_reason": None,
        "minute": minute,
        "minutes_remaining": minutes_remaining,
        "remaining_fraction": round(rem_frac or 0, 4),
        "block_2h_minute": settings.live_block_2h_minute,
        "min_model_prob": min_prob,
        "markets": markets,
        "chart": {
            "categories": [r["category_label"] for r in chart_rows],
            "probabilities_pct": [round(r["model_prob"] * 100, 1) for r in chart_rows],
            "ev_pct": [round(r["expected_value"] * 100, 1) for r in chart_rows],
        },
    }


__all__ = ["build_viable_2h_markets"]
