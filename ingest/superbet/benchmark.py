"""Comparação modelo vs mercado Superbet."""
from __future__ import annotations

from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot


def h2h_overround(h2h_odds: dict[str, float]) -> float | None:
    """Margem bruta do mercado 1X2: soma(1/odd) - 1."""
    prices = [h2h_odds[k] for k in ("1", "X", "2") if k in h2h_odds and h2h_odds[k] > 1.0]
    if len(prices) < 2:
        return None
    return round(sum(1.0 / p for p in prices) - 1.0, 4)


def market_benchmark(
    snapshot: SuperbetEventSnapshot,
    *,
    model_h2h: dict[str, float],
    model_totals: dict[str, float] | None = None,
    model_corners: dict[str, float] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source": "superbet",
        "event_id": snapshot.event_id,
        "h2h": {},
        "totals": {},
        "corners": {},
    }
    for key in ("1", "X", "2"):
        market_p = snapshot.h2h_implied.get(key)
        model_p = model_h2h.get(key)
        if market_p is None or model_p is None:
            continue
        out["h2h"][key] = {
            "market": round(market_p, 4),
            "model": round(model_p, 4),
            "edge": round(model_p - market_p, 4),
            "odds": snapshot.h2h_odds.get(key),
        }

    if model_totals:
        for line, market_probs in snapshot.totals_implied.items():
            over_key = next((k for k in market_probs if "mais" in k.lower() or "over" in k.lower()), None)
            if not over_key:
                continue
            model_over = model_totals.get(f"over_{line}".replace(".", "_"))
            if model_over is None:
                continue
            out["totals"][line] = {
                "market_over": round(market_probs[over_key], 4),
                "model_over": round(model_over, 4),
                "edge_over": round(model_over - market_probs[over_key], 4),
            }

    if model_corners and snapshot.corners_implied:
        for line, market_probs in snapshot.corners_implied.items():
            over_key = next((k for k in market_probs if "mais" in k.lower()), None)
            if not over_key:
                continue
            model_over = model_corners.get(f"over_{line}".replace(".", "_"))
            if model_over is None:
                continue
            out["corners"][line] = {
                "market_over": round(market_probs[over_key], 4),
                "model_over": round(model_over, 4),
                "edge_over": round(model_over - market_probs[over_key], 4),
            }

    return out
