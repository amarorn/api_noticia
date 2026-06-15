"""Bilhetes in-play separados por 1º/2º tempo e combos mistos."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from config import settings
from models.inplay_leg_compatibility import (
    combo_legs_compatible,
    is_superbet_bet_builder_market,
    legs_compatible as _markets_compatible,
)
from models.inplay_market_period import allow_2h_suggestions


def _period_of_market(market: str) -> str:
    if market.startswith("1h_"):
        return "1h"
    if market.startswith("2h_"):
        return "2h"
    return "ft"


def _leg_family(market: str) -> str:
    if market.endswith("_h2h") or market == "h2h":
        return "h2h"
    if "cs_" in market or "exact" in market or "over_" in market:
        return "goals"
    if "hcap" in market or "_ah_" in market:
        return "handicap"
    return "other"


def _legs_compatible(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Evita duplas correlacionadas ou impossíveis no Criar Aposta Superbet."""
    return _markets_compatible(
        a["market"],
        str(a.get("outcome") or "yes"),
        b["market"],
        str(b.get("outcome") or "yes"),
    )


def _serialize_leg(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "market": row["market"],
        "outcome": row["outcome"],
        "label": row["label"],
        "model_prob": row["model_prob"],
        "market_odd": row["market_odd"],
        "expected_value": row["expected_value"],
        "edge_pp": row["edge_pp"],
        "suggested_stake_pct": row.get("suggested_stake_pct"),
        "suggested_stake_value": row.get("suggested_stake_value"),
    }


def _build_combo(
    legs: list[dict[str, Any]],
    *,
    title: str,
    combo_id: str,
    bankroll: float,
) -> dict[str, Any]:
    combined_odd = 1.0
    combined_prob = 1.0
    for leg in legs:
        combined_odd *= float(leg["market_odd"])
        combined_prob *= float(leg["model_prob"])
    combined_ev = combined_prob * combined_odd - 1.0
    min_kelly = min(float(leg.get("suggested_stake_pct") or 1.0) for leg in legs)
    stake_pct = round(min(3.0, min_kelly * 0.55), 2)
    notes = [
        "Probabilidades tratadas como independentes — em mercados correlacionados o hit rate real pode ser menor.",
    ]
    if len(legs) > 1 and any(_period_of_market(l["market"]) != _period_of_market(legs[0]["market"]) for l in legs[1:]):
        notes.append("Bilhete misto: palpites de períodos diferentes — monte na Superbet como múltipla.")
    return {
        "id": combo_id,
        "title": title,
        "legs": [_serialize_leg(leg) for leg in legs],
        "combined_odd": round(combined_odd, 2),
        "combined_prob": round(combined_prob, 4),
        "combined_ev": round(combined_ev, 4),
        "suggested_stake_pct": stake_pct,
        "suggested_stake_value": round(bankroll * stake_pct / 100, 2),
        "notes": notes,
    }


def _pick_combos(
    pool: list[dict[str, Any]],
    *,
    prefix: str,
    title_prefix: str,
    bankroll: float,
    max_combos: int = 2,
) -> list[dict[str, Any]]:
    if len(pool) < 2:
        return []
    combos: list[dict[str, Any]] = []
    for a, b in combinations(pool[:6], 2):
        if not _legs_compatible(a, b):
            continue
        combo = _build_combo(
            [a, b],
            title=f"{title_prefix} — dupla",
            combo_id=f"{prefix}-double",
            bankroll=bankroll,
        )
        if combo["combined_ev"] <= 0:
            continue
        combos.append(combo)
    combos.sort(key=lambda c: c["combined_ev"], reverse=True)
    # ids únicos
    for idx, combo in enumerate(combos[:max_combos], start=1):
        combo["id"] = f"{prefix}-double-{idx}"
    return combos[:max_combos]


def _period_block(
    rows: list[dict[str, Any]],
    *,
    period: str,
    minute: int,
    bankroll: float,
    title: str,
    closed_after_minute: int | None,
) -> dict[str, Any]:
    closed = closed_after_minute is not None and minute > closed_after_minute
    period_rows = [r for r in rows if _period_of_market(r["market"]) == period]
    qualified = [r for r in period_rows if r.get("meets_threshold")]
    pool = qualified if qualified else period_rows[:4]

    pool = [
        r for r in pool
        if is_superbet_bet_builder_market(r["market"])
    ]

    singles = [_serialize_leg(r) for r in pool[:4]]
    combos = [] if closed else _pick_combos(
        pool,
        prefix=period,
        title_prefix=title,
        bankroll=bankroll,
    )

    closed_reason = None
    if closed:
        closed_reason = f"Mercados do {title.lower()} encerrados após o intervalo."
    elif not singles:
        closed_reason = f"Sem edge nos mercados do {title.lower()} neste refresh."

    return {
        "available": not closed and bool(singles),
        "closed": closed,
        "closed_reason": closed_reason,
        "singles": singles,
        "combos": combos,
    }


def build_inplay_half_tickets(
    market_scan: list[dict[str, Any]],
    *,
    minute: int,
    bankroll: float = 1000.0,
) -> dict[str, Any]:
    """Monta sugestões de bilhetes simples e múltiplas por período."""
    if minute > settings.live_block_2h_minute:
        return {
            "first_half": {
                "available": False,
                "closed": True,
                "closed_reason": "Jogo avançado — sem novos bilhetes.",
                "singles": [],
                "combos": [],
            },
            "second_half": {
                "available": False,
                "closed": True,
                "closed_reason": "Jogo avançado — sem novos bilhetes.",
                "singles": [],
                "combos": [],
            },
            "mixed_combos": [],
        }

    first_half = _period_block(
        market_scan,
        period="1h",
        minute=minute,
        bankroll=bankroll,
        title="1º Tempo",
        closed_after_minute=45,
    )
    second_half = _period_block(
        market_scan,
        period="2h",
        minute=minute,
        bankroll=bankroll,
        title="2º Tempo",
        closed_after_minute=settings.live_block_2h_minute if not allow_2h_suggestions(minute) else None,
    )

    mixed: list[dict[str, Any]] = []
    if minute <= 45:
        pool_1h = [r for r in market_scan if _period_of_market(r["market"]) == "1h" and r.get("meets_threshold")]
        pool_2h = [r for r in market_scan if _period_of_market(r["market"]) == "2h" and r.get("meets_threshold")]
        if not pool_1h:
            pool_1h = [r for r in market_scan if _period_of_market(r["market"]) == "1h"][:3]
        if not pool_2h:
            pool_2h = [r for r in market_scan if _period_of_market(r["market"]) == "2h"][:3]
        if pool_1h and pool_2h:
            for idx, (a, b) in enumerate(zip(pool_1h[:3], pool_2h[:3], strict=False), start=1):
                if not _legs_compatible(a, b):
                    continue
                combo = _build_combo(
                    [a, b],
                    title="Misto 1T + 2T",
                    combo_id=f"mixed-{idx}",
                    bankroll=bankroll,
                )
                if combo["combined_ev"] > 0:
                    mixed.append(combo)
            mixed.sort(key=lambda c: c["combined_ev"], reverse=True)
            mixed = mixed[:2]

    return {
        "first_half": first_half,
        "second_half": second_half,
        "mixed_combos": mixed,
    }


__all__ = ["build_inplay_half_tickets"]
