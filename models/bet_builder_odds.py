"""Odd combinada do Criar Aposta Superbet (SGM) — correlação vs produto simples."""

from __future__ import annotations

from typing import Any

from models.inplay_leg_compatibility import combo_legs_compatible, period_of_market

_YES_OUTCOMES = frozenset({"yes", "sim", "over", "1", "home", "away"})
_NO_OUTCOMES = frozenset({"no", "não", "nao", "under", "2", "x", "draw"})


def round_combo_odd(value: float) -> float:
    return round(float(value), 2)


def _is_yes_outcome(outcome: str) -> bool:
    return (outcome or "").strip().lower() in _YES_OUTCOMES


def _is_under_outcome(outcome: str) -> bool:
    o = (outcome or "").strip().lower()
    return o in _NO_OUTCOMES or o == "under"


def _is_goals_total_market(market: str) -> bool:
    body = market[3:] if market.startswith(("1h_", "2h_", "ft_")) else market
    return (
        body.startswith("over_")
        or body.startswith("home_over_")
        or body.startswith("away_over_")
    )


def narrative_correlation_boost(legs: list[dict[str, Any]]) -> float:
    """Boost em P(indep) para aproximar preço SGM quando pernas são correlacionadas."""
    if len(legs) < 2:
        return 1.0

    markets = [str(leg.get("market") or "") for leg in legs]
    outcomes = [str(leg.get("outcome") or "yes") for leg in legs]
    boost = 1.0

    # Unders aninhados (ex.: FT under 3.5 + 1T under 2.5) — alta correlação positiva
    if all(_is_under_outcome(o) for o in outcomes) and all(_is_goals_total_market(m) for m in markets):
        periods = {period_of_market(m) for m in markets}
        if len(periods) >= 2 or ("1h" in periods and "ft" in periods):
            boost = max(boost, 1.38)
        else:
            boost = max(boost, 1.22)

    # Overs correlacionados (ex.: over 2.5 + BTTS sim)
    if any(m == "btts" for m in markets) and any(_is_goals_total_market(m) for m in markets):
        btts_yes = any(m == "btts" and _is_yes_outcome(o) for m, o in zip(markets, outcomes, strict=True))
        over_yes = any(
            _is_goals_total_market(m) and _is_yes_outcome(o) for m, o in zip(markets, outcomes, strict=True)
        )
        if btts_yes and over_yes:
            boost = max(boost, 1.28)

    # Mesmo período, mesma família (ex.: dois overs de gols no 1T)
    if len(markets) == 2:
        p0, p1 = period_of_market(markets[0]), period_of_market(markets[1])
        if p0 == p1 and all(_is_yes_outcome(o) for o in outcomes):
            if all(_is_goals_total_market(m) for m in markets):
                boost = max(boost, 1.18)

    return boost


def _same_event_bet_builder(legs: list[dict[str, Any]]) -> bool:
    event_ids = {leg.get("superbet_event_id") for leg in legs if leg.get("superbet_event_id") is not None}
    if len(event_ids) != 1:
        return False
    pairs = [(str(leg.get("market") or ""), str(leg.get("outcome") or "yes")) for leg in legs]
    return combo_legs_compatible(pairs)


def product_odds(legs: list[dict[str, Any]]) -> float:
    product = 1.0
    for leg in legs:
        product *= float(leg.get("market_odd") or 0)
    return round_combo_odd(product)


def resolve_combined_odds(
    legs: list[dict[str, Any]],
    *,
    force_product: bool = False,
) -> tuple[float, float, str]:
    """Retorna (odd_final, odd_produto_simples, pricing_mode).

    pricing_mode:
    - ``product`` — múltipla cross-event ou pernas independentes
    - ``bet_builder_sgm`` — Criar Aposta mesma partida (correlação via modelo)
    - ``bet_builder_heuristic`` — SGM sem model_prob (desconto heurístico)
    """
    simple = product_odds(legs)
    if force_product or len(legs) < 2:
        return simple, simple, "product"

    if not _same_event_bet_builder(legs):
        return simple, simple, "product"

    probs = [leg.get("model_prob") for leg in legs]
    if all(p is not None and float(p) > 0 for p in probs):
        indep_prob = 1.0
        for p in probs:
            indep_prob *= float(p)
        boost = narrative_correlation_boost(legs)
        joint_prob = min(0.95, indep_prob * boost)
        sgm_odd = round_combo_odd(1.0 / joint_prob)
        final = min(simple, sgm_odd)
        return final, simple, "bet_builder_sgm"

    boost = narrative_correlation_boost(legs)
    if boost > 1.05:
        discount = 1.0 / boost
        final = round_combo_odd(simple * discount)
        return final, simple, "bet_builder_heuristic"

    return simple, simple, "product"


__all__ = [
    "narrative_correlation_boost",
    "product_odds",
    "resolve_combined_odds",
    "round_combo_odd",
]
