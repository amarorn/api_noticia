"""Sugestões de Super Múltipla a partir do market_scan in-play."""

from __future__ import annotations

import uuid
from itertools import combinations
from typing import Any

from config import settings
from models.inplay_leg_compatibility import combo_legs_compatible, is_superbet_bet_builder_market
from models.super_multipla import calculate_multiple_odds, calculate_super_multipla
from schemas.super_multipla import SuperMultiplaCalculateRequest, SuperMultiplaLegInput


def _row_to_leg(row: dict[str, Any], *, event_id: int, is_live: bool, minute: int) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "market": str(row.get("market") or ""),
        "outcome": str(row.get("outcome") or "yes"),
        "market_odd": float(row.get("market_odd") or 0),
        "model_prob": float(row.get("model_prob") or 0),
        "expected_value": float(row.get("expected_value") or 0),
        "edge_pp": float(row.get("edge_pp") or 0),
        "superbet_event_id": event_id,
        "selection_label": str(row.get("label") or ""),
        "is_live": is_live,
        "minute": minute,
    }


def build_super_multipla_block(
    market_scan: list[dict[str, Any]],
    *,
    superbet_event_id: int,
    minute: int = 0,
    home_score: int = 0,
    away_score: int = 0,
    is_live: bool = True,
    stake: float | None = None,
    max_combos: int = 4,
    min_combined_odd: float = 3.0,
    min_leg_odd: float | None = None,
) -> dict[str, Any]:
    """Monta bloco ``super_multipla`` para o payload de advice."""
    stake_val = float(stake or settings.bet_default_stake_brl)
    min_odd = float(min_leg_odd or settings.super_multipla_min_leg_odd)

    pool: list[dict[str, Any]] = []
    for row in market_scan:
        market = str(row.get("market") or "")
        odd = float(row.get("market_odd") or 0)
        if not market or not is_superbet_bet_builder_market(market):
            continue
        if odd < min_odd:
            continue
        pool.append(row)

    pool.sort(key=lambda r: float(r.get("model_prob") or 0), reverse=True)
    pool = pool[:24]

    candidates: list[tuple[float, list[dict[str, Any]]]] = []
    seen: set[str] = set()

    for left, right in combinations(pool, 2):
        pairs = [
            (str(left.get("market") or ""), str(left.get("outcome") or "yes")),
            (str(right.get("market") or ""), str(right.get("outcome") or "yes")),
        ]
        if not combo_legs_compatible(pairs):
            continue
        legs = [
            _row_to_leg(left, event_id=superbet_event_id, is_live=is_live, minute=minute),
            _row_to_leg(right, event_id=superbet_event_id, is_live=is_live, minute=minute),
        ]
        key = "|".join(sorted(f"{leg['market']}:{leg['outcome']}" for leg in legs))
        if key in seen:
            continue
        seen.add(key)
        try:
            total_odds = calculate_multiple_odds(legs)
        except Exception:
            continue
        if total_odds < min_combined_odd:
            continue
        combined_prob = float(legs[0].get("model_prob") or 0) * float(legs[1].get("model_prob") or 0)
        candidates.append((combined_prob, legs))

    candidates.sort(key=lambda item: item[0], reverse=True)

    suggested: list[dict[str, Any]] = []
    for combined_prob, legs in candidates[: max_combos * 2]:
        if len(suggested) >= max_combos:
            break
        calc_legs = [SuperMultiplaLegInput(**leg) for leg in legs]
        try:
            calc = calculate_super_multipla(
                SuperMultiplaCalculateRequest(
                    legs=calc_legs,
                    stake=stake_val,
                    bet_type="MULTIPLE",
                    minute=minute,
                    home_score=home_score,
                    away_score=away_score,
                    superbet_event_id=superbet_event_id,
                )
            )
        except Exception:
            continue

        combined_prob = calc.combined_prob if calc.combined_prob is not None else combined_prob
        suggested.append({
            "id": str(uuid.uuid4()),
            "legs": [
                {
                    **leg,
                    "label": leg.get("selection_label") or "",
                    "market_odd": leg["market_odd"],
                    "model_prob": leg["model_prob"],
                }
                for leg in legs
            ],
            "stake": stake_val,
            "combined_odd": calc.total_odds,
            "product_odd": calc.product_odds,
            "pricing_mode": calc.pricing_mode,
            "combined_prob": combined_prob,
            "combined_ev": calc.combined_ev,
            "potential_payout": calc.potential_payout,
            "bonus_eligible": calc.bonus_eligible,
            "bonus_percentage": calc.bonus_percentage,
            "final_payout": calc.final_payout,
            "warnings": calc.warnings,
            "builder_validation": calc.builder_validation,
        })

    return {
        "min_leg_odd_for_bonus": min_odd,
        "bonus_pct": float(settings.super_multipla_bonus_pct),
        "default_stake": stake_val,
        "suggested_combos": suggested,
    }


__all__ = ["build_super_multipla_block"]
