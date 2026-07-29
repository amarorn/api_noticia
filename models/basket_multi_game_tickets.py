"""Monta bilhetes cross-game de basquete (1 palpite por jogo, múltipla independente)."""

from __future__ import annotations

import uuid
from itertools import combinations
from typing import Any

from config import settings
from models.bet_decision import compute_conservative_stake
from models.super_multipla import calculate_super_multipla
from schemas.super_multipla import SuperMultiplaCalculateRequest, SuperMultiplaEventContext, SuperMultiplaLegInput


def _parse_score(score: str | None) -> tuple[int, int]:
    if not score:
        return 0, 0
    parts = str(score).replace("×", "-").replace("x", "-").split("-")
    if len(parts) != 2:
        return 0, 0
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except ValueError:
        return 0, 0


def _aporte_sort_key(aporte: dict[str, Any]) -> tuple[int, float]:
    action_rank = 1 if aporte.get("action") == "apostar" else 0
    return action_rank, float(aporte.get("expected_value") or 0.0)


def pick_best_leg_from_advice(
    advice: dict[str, Any],
    *,
    require_apostar: bool = False,
) -> dict[str, Any] | None:
    """Escolhe a melhor perna de um jogo (prioriza action=apostar e maior EV)."""
    aportes = list(advice.get("aportes") or [])
    if not aportes:
        return None

    pool = [a for a in aportes if a.get("action") == "apostar"] if require_apostar else aportes
    if not pool:
        pool = aportes

    best = max(pool, key=_aporte_sort_key)
    event_id = int(advice.get("superbet_event_id") or 0)
    home = str(advice.get("home_team") or "")
    away = str(advice.get("away_team") or "")
    home_score, away_score = _parse_score(advice.get("current_score"))

    return {
        "superbet_event_id": event_id,
        "event_name": f"{home} vs {away}".strip(),
        "home_team": home,
        "away_team": away,
        "minute": int(advice.get("minute") or 0),
        "home_score": home_score,
        "away_score": away_score,
        "is_live": bool(advice.get("is_live")),
        "market": str(best.get("market") or ""),
        "outcome": str(best.get("outcome") or ""),
        "label": str(best.get("label") or ""),
        "market_display": str(best.get("market_display") or best.get("label") or ""),
        "model_prob": float(best.get("model_prob") or 0.0),
        "market_odd": float(best.get("market_odd") or 0.0),
        "expected_value": float(best.get("expected_value") or 0.0),
        "edge_pp": float(best.get("edge_pp") or 0.0),
        "kelly_quarter": float(best.get("kelly_quarter") or 0.0),
        "action": str(best.get("action") or "monitorar"),
    }


def _leg_to_super_multipla_input(leg: dict[str, Any]) -> SuperMultiplaLegInput:
    return SuperMultiplaLegInput(
        id=str(uuid.uuid4()),
        market=leg["market"],
        outcome=leg["outcome"],
        market_odd=float(leg["market_odd"]),
        model_prob=float(leg["model_prob"]),
        superbet_event_id=int(leg["superbet_event_id"]),
        event_name=leg.get("event_name"),
        selection_label=leg.get("label"),
        is_live=bool(leg.get("is_live")),
        minute=int(leg.get("minute") or 0),
    )


def _ticket_score(combined_ev: float | None, combined_prob: float | None, combined_odd: float) -> float:
    ev = float(combined_ev or 0.0)
    prob = float(combined_prob or 0.0)
    if ev <= 0:
        return ev
    return ev * max(prob, 0.01) * min(combined_odd, 50.0)


def build_basket_multi_game_tickets(
    advice_by_event: dict[int, dict[str, Any]],
    *,
    bankroll: float = 1000.0,
    stake: float | None = None,
    min_legs: int = 2,
    max_legs: int = 4,
    max_tickets: int = 5,
    require_apostar: bool = False,
    min_combined_ev: float | None = None,
) -> dict[str, Any]:
    """Gera bilhetes sugeridos a partir de advice por event_id."""
    min_legs = max(2, min(min_legs, max_legs))
    max_legs = max(min_legs, max_legs)
    stake_val = float(stake or settings.bet_default_stake_brl)
    min_ev = float(min_combined_ev if min_combined_ev is not None else settings.ev_min_edge)

    per_game_best: list[dict[str, Any]] = []
    skipped_events: list[dict[str, Any]] = []

    for event_id, advice in sorted(advice_by_event.items()):
        leg = pick_best_leg_from_advice(advice, require_apostar=require_apostar)
        if leg is None:
            skipped_events.append(
                {
                    "event_id": event_id,
                    "reason": "sem_aportes",
                    "home_team": advice.get("home_team"),
                    "away_team": advice.get("away_team"),
                }
            )
            continue
        per_game_best.append(leg)

    suggested: list[dict[str, Any]] = []
    if len(per_game_best) >= min_legs:
        event_contexts = [
            SuperMultiplaEventContext(
                superbet_event_id=int(leg["superbet_event_id"]),
                minute=int(leg.get("minute") or 0),
                home_score=int(leg.get("home_score") or 0),
                away_score=int(leg.get("away_score") or 0),
            )
            for leg in per_game_best
        ]

        candidates: list[tuple[float, dict[str, Any]]] = []
        for size in range(min_legs, min(max_legs, len(per_game_best)) + 1):
            for combo in combinations(per_game_best, size):
                legs = list(combo)
                sm_legs = [_leg_to_super_multipla_input(leg) for leg in legs]
                try:
                    calc = calculate_super_multipla(
                        SuperMultiplaCalculateRequest(
                            legs=sm_legs,
                            stake=stake_val,
                            bet_type="MULTIPLE",
                            event_contexts=event_contexts,
                        )
                    )
                except Exception:
                    continue

                combined_ev = calc.combined_ev
                if combined_ev is not None and combined_ev < min_ev:
                    continue

                avg_kelly = sum(float(leg.get("kelly_quarter") or 0.0) for leg in legs) / len(legs)
                stake_brl, stake_pct = compute_conservative_stake(
                    bankroll=bankroll,
                    kelly_quarter=avg_kelly,
                    classification="value_bet" if combined_ev and combined_ev > min_ev * 2 else "watch",
                )

                score = _ticket_score(combined_ev, calc.combined_prob, calc.total_odds)
                ticket = {
                    "ticket_id": str(uuid.uuid4()),
                    "legs": [
                        {
                            "superbet_event_id": leg["superbet_event_id"],
                            "event_name": leg["event_name"],
                            "home_team": leg["home_team"],
                            "away_team": leg["away_team"],
                            "minute": leg["minute"],
                            "is_live": leg["is_live"],
                            "market": leg["market"],
                            "outcome": leg["outcome"],
                            "label": leg["label"],
                            "market_display": leg.get("market_display") or leg["label"],
                            "model_prob": round(float(leg["model_prob"]), 4),
                            "market_odd": round(float(leg["market_odd"]), 2),
                            "expected_value": round(float(leg["expected_value"]), 4),
                            "edge_pp": round(float(leg["edge_pp"]), 2),
                            "action": leg["action"],
                        }
                        for leg in legs
                    ],
                    "combined_odd": calc.total_odds,
                    "product_odds": calc.product_odds,
                    "pricing_mode": calc.pricing_mode,
                    "combined_prob": calc.combined_prob,
                    "combined_ev": combined_ev,
                    "stake_brl": stake_brl,
                    "stake_pct": stake_pct,
                    "potential_payout": calc.potential_payout,
                    "final_payout": calc.final_payout,
                    "bonus_eligible": calc.bonus_eligible,
                    "bonus_percentage": calc.bonus_percentage,
                    "score": round(score, 4),
                    "warnings": calc.warnings,
                }
                candidates.append((score, ticket))

        candidates.sort(key=lambda item: item[0], reverse=True)
        seen_keys: set[str] = set()
        for _score, ticket in candidates:
            key = "|".join(
                sorted(f"{leg['superbet_event_id']}:{leg['market']}:{leg['outcome']}" for leg in ticket["legs"])
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            suggested.append(ticket)
            if len(suggested) >= max_tickets:
                break

    return {
        "event_ids": sorted(advice_by_event.keys()),
        "games_evaluated": len(advice_by_event),
        "games_with_pick": len(per_game_best),
        "skipped_events": skipped_events,
        "per_game_best": per_game_best,
        "suggested_tickets": suggested,
        "bankroll": bankroll,
        "stake": stake_val,
        "min_legs": min_legs,
        "max_legs": max_legs,
    }


__all__ = ["build_basket_multi_game_tickets", "pick_best_leg_from_advice"]
