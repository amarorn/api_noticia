"""Cálculo e validação de Super Múltipla (odds combinadas + bônus promo Superbet)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from config import settings
from models.bet_builder_odds import resolve_combined_odds
from models.inplay_bet_builder_guard import validate_bet_builder
from schemas.super_multipla import (
    SuperMultiplaCalculateRequest,
    SuperMultiplaCalculateResponse,
    SuperMultiplaEventContext,
)
from schemas.user_bet import UserOpenBetRequest

MIN_LEG_ODD = 1.01
MIN_STAKE_BRL = 1.0


class SuperMultiplaValidationError(ValueError):
    """Violação de invariante de slip (odds, stake, tipo de aposta)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def round_money(value: float) -> float:
    """Arredonda valor monetário para centavos (0 erro de centavo em testes)."""
    return round(float(value), 2)


def calculate_multiple_odds(legs: list[dict[str, Any]]) -> float:
    """Odd combinada: produto simples ou SGM (Criar Aposta mesma partida)."""
    if len(legs) < 2:
        raise SuperMultiplaValidationError(
            "min_legs",
            "Múltipla exige pelo menos 2 pernas.",
        )
    for idx, leg in enumerate(legs, start=1):
        odd = float(leg.get("market_odd") or 0)
        if odd < MIN_LEG_ODD:
            raise SuperMultiplaValidationError(
                "min_leg_odd",
                f"Perna {idx}: odd mínima {MIN_LEG_ODD:.2f} (recebido {odd:.2f}).",
            )
    final, _simple, _mode = resolve_combined_odds(legs)
    return final


def calculate_multiple_odds_detail(legs: list[dict[str, Any]]) -> tuple[float, float, str]:
    """Retorna (odd_final, odd_produto, pricing_mode) com validação de pernas."""
    if len(legs) < 2:
        raise SuperMultiplaValidationError(
            "min_legs",
            "Múltipla exige pelo menos 2 pernas.",
        )
    for idx, leg in enumerate(legs, start=1):
        odd = float(leg.get("market_odd") or 0)
        if odd < MIN_LEG_ODD:
            raise SuperMultiplaValidationError(
                "min_leg_odd",
                f"Perna {idx}: odd mínima {MIN_LEG_ODD:.2f} (recebido {odd:.2f}).",
            )
    return resolve_combined_odds(legs)


def validate_super_multipla_bonus(legs: list[dict[str, Any]]) -> tuple[bool, float]:
    """Elegibilidade promo Super Múltipla (+5% default se todas pernas >= 1.35)."""
    min_odd = float(settings.super_multipla_min_leg_odd)
    bonus_pct = float(settings.super_multipla_bonus_pct)
    if len(legs) < 2:
        return False, 0.0
    eligible = all(float(leg.get("market_odd") or 0) >= min_odd for leg in legs)
    return eligible, bonus_pct if eligible else 0.0


def calculate_payout(
    stake: float,
    total_odds: float,
    bonus_percentage: float,
) -> tuple[float, float]:
    """Retorna (potential_payout, final_payout) com bônus aplicado sobre o bruto."""
    if stake <= 0:
        raise SuperMultiplaValidationError("min_stake", "Stake deve ser maior que zero.")
    if total_odds <= 0:
        raise SuperMultiplaValidationError("invalid_odds", "Odd total inválida.")
    potential = round_money(stake * total_odds)
    final = round_money(potential * (1.0 + bonus_percentage))
    return potential, final


def _combined_model_metrics(
    legs: list[dict[str, Any]],
    total_odds: float,
    *,
    joint_model_prob: float | None = None,
) -> tuple[float | None, float | None]:
    if joint_model_prob is not None:
        combined_ev = joint_model_prob * total_odds - 1.0
        return round(joint_model_prob, 6), round(combined_ev, 4)
    probs: list[float] = []
    for leg in legs:
        prob = leg.get("model_prob")
        if prob is None:
            return None, None
        probs.append(float(prob))
    combined_prob = 1.0
    for p in probs:
        combined_prob *= p
    combined_ev = combined_prob * total_odds - 1.0
    return round(combined_prob, 6), round(combined_ev, 4)


def _joint_model_prob(legs: list[dict[str, Any]], pricing_mode: str) -> float | None:
    if not pricing_mode.startswith("bet_builder"):
        return None
    from models.bet_builder_odds import narrative_correlation_boost

    probs = [leg.get("model_prob") for leg in legs]
    if not all(p is not None and float(p) > 0 for p in probs):
        return None
    indep = 1.0
    for p in probs:
        indep *= float(p)
    boost = narrative_correlation_boost(legs)
    return min(0.95, indep * boost)


def _resolve_event_context(
    event_id: int,
    req: SuperMultiplaCalculateRequest,
) -> SuperMultiplaEventContext:
    for ctx in req.event_contexts:
        if ctx.superbet_event_id == event_id:
            return ctx
    return SuperMultiplaEventContext(
        superbet_event_id=event_id,
        minute=req.minute,
        home_score=req.home_score,
        away_score=req.away_score,
        ht_home_score=req.ht_home_score,
        ht_away_score=req.ht_away_score,
    )


def _builder_validation_by_event(
    legs: list[dict[str, Any]],
    req: SuperMultiplaCalculateRequest,
    total_odds: float,
) -> dict[str, dict[str, Any]]:
    """Valida Criar Aposta por evento quando há 2+ pernas no mesmo jogo."""
    by_event: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for leg in legs:
        eid = leg.get("superbet_event_id")
        if eid is not None:
            by_event[int(eid)].append(leg)

    result: dict[str, dict[str, Any]] = {}
    for event_id, group in by_event.items():
        if len(group) < 2:
            continue
        ctx = _resolve_event_context(event_id, req)
        builder_legs = [
            {
                "market": leg.get("market", ""),
                "outcome": leg.get("outcome", "yes"),
                "label": leg.get("selection_label") or leg.get("label"),
            }
            for leg in group
        ]
        result[str(event_id)] = validate_bet_builder(
            builder_legs,
            minute=ctx.minute,
            home_score=ctx.home_score,
            away_score=ctx.away_score,
            ht_home=ctx.ht_home_score,
            ht_away=ctx.ht_away_score,
            combined_odd=total_odds,
        )
    return result


def _late_multi_warnings(legs: list[dict[str, Any]], req: SuperMultiplaCalculateRequest) -> list[str]:
    if not settings.bet_block_multis_late:
        return []
    block_minute = int(settings.live_block_minute)
    warnings: list[str] = []
    for leg in legs:
        minute = leg.get("minute")
        if minute is None and leg.get("superbet_event_id") is not None:
            ctx = _resolve_event_context(int(leg["superbet_event_id"]), req)
            minute = ctx.minute
        if minute is not None and int(minute) >= block_minute and leg.get("is_live"):
            warnings.append(
                f"Após {block_minute}' novas múltiplas ao vivo são bloqueadas (guardrail P0). "
                "Considere apenas cash-out ou simples."
            )
            break
    return warnings


def _validate_stake(stake: float) -> None:
    if stake < MIN_STAKE_BRL:
        raise SuperMultiplaValidationError(
            "min_stake",
            f"Stake mínima R$ {MIN_STAKE_BRL:.2f}.",
        )
    max_stake = float(settings.bet_max_stake)
    if stake > max_stake:
        raise SuperMultiplaValidationError(
            "max_stake",
            f"Stake máxima R$ {max_stake:.2f} (bet_max_stake).",
        )


def calculate_super_multipla(req: SuperMultiplaCalculateRequest) -> SuperMultiplaCalculateResponse:
    """Orquestra cálculo de odds, prêmio, bônus e validações de builder."""
    legs = [leg.model_dump() for leg in req.legs]
    bet_type = req.bet_type

    if bet_type == "MULTIPLE" and len(legs) < 2:
        raise SuperMultiplaValidationError(
            "min_legs",
            "bet_type=MULTIPLE exige pelo menos 2 pernas.",
        )

    _validate_stake(float(req.stake))

    if bet_type == "SIMPLE":
        if len(legs) != 1:
            raise SuperMultiplaValidationError(
                "simple_legs",
                "Aposta simples exige exatamente 1 perna.",
            )
        odd = float(legs[0].get("market_odd") or 0)
        if odd < MIN_LEG_ODD:
            raise SuperMultiplaValidationError("min_leg_odd", f"Odd mínima {MIN_LEG_ODD:.2f}.")
        total_odds = round_money(odd)
        product_odds_val = total_odds
        pricing_mode = "product"
        joint_model_prob = None
    else:
        total_odds, product_odds_val, pricing_mode = calculate_multiple_odds_detail(legs)
        joint_model_prob = _joint_model_prob(legs, pricing_mode)

    bonus_eligible, bonus_pct = validate_super_multipla_bonus(legs)
    potential_payout, final_payout = calculate_payout(float(req.stake), total_odds, bonus_pct)
    combined_prob, combined_ev = _combined_model_metrics(
        legs, total_odds, joint_model_prob=joint_model_prob
    )

    warnings = _late_multi_warnings(legs, req)
    if pricing_mode.startswith("bet_builder") and product_odds_val > total_odds + 0.05:
        warnings.append(
            f"Criar Aposta Superbet: odd combinada @{total_odds:.2f} "
            f"(não @{product_odds_val:.2f} produto das simples — pernas correlacionadas)."
        )
    builder_validation = _builder_validation_by_event(legs, req, total_odds)

    for _event_id, validation in builder_validation.items():
        if not validation.get("valid"):
            for err in validation.get("errors", []):
                reason = err.get("reason") or err.get("title") or "Combo inválido"
                warnings.append(f"Criar Aposta: {reason}")

    return SuperMultiplaCalculateResponse(
        slip_id=req.slip_id,
        total_odds=total_odds,
        product_odds=product_odds_val,
        pricing_mode=pricing_mode,
        potential_payout=potential_payout,
        bonus_eligible=bonus_eligible,
        bonus_percentage=bonus_pct,
        final_payout=final_payout,
        combined_prob=combined_prob,
        combined_ev=combined_ev,
        currency="BRL",
        warnings=warnings,
        builder_validation=builder_validation or None,
        bet_type=bet_type,
        legs_count=len(legs),
    )


def enrich_open_bet_with_super_multipla(req: UserOpenBetRequest) -> dict[str, Any]:
    """Recalcula métricas de múltipla para cadastro em /user/open-bets."""
    legs = [p.model_dump() for p in req.picks]
    for leg in legs:
        if leg.get("market_odd") is None:
            leg["market_odd"] = float(req.odds_placed)

    bet_type = "MULTIPLE" if len(legs) >= 2 else "SIMPLE"

    if bet_type == "MULTIPLE":
        total_odds, product_odds_val, pricing_mode = calculate_multiple_odds_detail(legs)
        joint_model_prob = _joint_model_prob(legs, pricing_mode)
        bonus_eligible, bonus_pct = validate_super_multipla_bonus(legs)
        potential_payout, final_payout = calculate_payout(req.stake, total_odds, bonus_pct)
        combined_prob, combined_ev = _combined_model_metrics(
            legs, total_odds, joint_model_prob=joint_model_prob
        )
    else:
        total_odds = round_money(float(legs[0].get("market_odd") or req.odds_placed))
        bonus_eligible, bonus_pct = False, 0.0
        potential_payout, final_payout = calculate_payout(req.stake, total_odds, 0.0)
        combined_prob, combined_ev = _combined_model_metrics(legs, total_odds)

    return {
        "total_odds": total_odds,
        "potential_payout": potential_payout,
        "final_payout": final_payout,
        "bonus_eligible": bonus_eligible,
        "bonus_percentage": bonus_pct,
        "combined_prob": combined_prob if combined_prob is not None else req.combined_prob,
        "combined_ev": combined_ev if combined_ev is not None else req.combined_ev,
    }


__all__ = [
    "SuperMultiplaValidationError",
    "calculate_multiple_odds",
    "calculate_payout",
    "calculate_super_multipla",
    "enrich_open_bet_with_super_multipla",
    "round_money",
    "validate_super_multipla_bonus",
]
