"""Benchmark modelo vs mercado Superbet (beisebol)."""
from __future__ import annotations

from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot


def _implied(odd: float) -> float | None:
    return round(1.0 / odd, 4) if odd > 1.0 else None


def baseball_market_benchmark(
    snapshot: SuperbetEventSnapshot,
    *,
    model_moneyline: dict[str, float],
    model_totals: dict[str, float] | None = None,
    model_spread: dict[str, float] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source": "superbet",
        "event_id": snapshot.event_id,
        "moneyline": {},
        "totals": {},
        "spread": {},
    }
    ml_implied = snapshot.moneyline_implied or snapshot.h2h_implied or {}
    ml_odds = snapshot.moneyline_odds or snapshot.h2h_odds or {}
    for key in ("1", "2"):
        market_p = ml_implied.get(key)
        model_p = model_moneyline.get(key)
        if market_p is None or model_p is None:
            continue
        out["moneyline"][key] = {
            "market": round(market_p, 4),
            "model": round(model_p, 4),
            "edge": round(model_p - market_p, 4),
            "odds": ml_odds.get(key),
        }

    if model_totals and snapshot.total_points_odds:
        for line_str, sides in snapshot.total_points_odds.items():
            over_odd = sides.get("over")
            if over_odd is None:
                continue
            market_p = _implied(over_odd)
            try:
                line_val = float(str(line_str).replace(",", "."))
            except (TypeError, ValueError):
                continue
            lk = f"{line_val:g}".replace(".", "_")
            model_over = (model_totals or {}).get(f"over_{lk}")
            if market_p is None or model_over is None:
                continue
            out["totals"][str(line_str)] = {
                "market_over": market_p,
                "model_over": round(model_over, 4),
                "edge_over": round(model_over - market_p, 4),
            }

    if model_spread and snapshot.spread_odds:
        for line_key, sides in snapshot.spread_odds.items():
            home_odd = sides.get("home")
            if home_odd is None:
                continue
            market_p = _implied(home_odd)
            prob_key = f"home_{line_key}"
            model_p = (model_spread or {}).get(prob_key)
            if market_p is None or model_p is None:
                continue
            out["spread"][line_key] = {
                "market_home_cover": market_p,
                "model_home_cover": round(model_p, 4),
                "edge_home": round(model_p - market_p, 4),
            }

    return out
