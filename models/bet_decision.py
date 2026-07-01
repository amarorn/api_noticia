"""Camada de decisão antes de exibir recomendações de aposta."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import settings
from models.bet_observability import (
    log_ev_calculated,
    log_recommendation_allowed,
    log_recommendation_blocked,
)

BLOCKED_MARKET_KEYS = frozenset({"unknown", "other", "", "combo"})


@dataclass
class BetDecision:
    allowed: bool
    classification: str
    reason: str | None = None
    suggested_stake_brl: float = 0.0
    suggested_stake_pct: float = 0.0
    use_kelly: bool = False


def normalize_market_key(market: str | None) -> str:
    return (market or "").strip().lower()


def is_blocked_market(market: str | None) -> bool:
    key = normalize_market_key(market)
    return key in BLOCKED_MARKET_KEYS or key.endswith("_unknown")


def classify_recommendation(
    *,
    ev: float,
    edge_pp: float,
    model_prob: float,
    confidence_score: float,
    threshold: float,
) -> str:
    if ev <= threshold:
        return "avoid"
    if (
        ev >= threshold * 2.5
        and edge_pp >= 12.0
        and model_prob >= 0.35
        and confidence_score >= 0.65
    ):
        return "high_confidence"
    if ev >= threshold * 1.5 and edge_pp >= 8.0:
        return "value_bet"
    if ev > threshold:
        return "watch"
    return "avoid"


def compute_conservative_stake(
    *,
    bankroll: float,
    kelly_quarter: float,
    classification: str,
    use_kelly: bool | None = None,
) -> tuple[float, float]:
    """Retorna (stake_brl, stake_pct)."""
    use_kelly_fraction = (
        settings.bet_use_fractional_kelly if use_kelly is None else use_kelly
    )
    max_stake = min(settings.bet_max_stake, bankroll * (settings.bet_max_stake_pct / 100.0))
    default_stake = min(settings.bet_default_stake_brl, max_stake)

    if not use_kelly_fraction or classification == "watch":
        pct = round((default_stake / bankroll) * 100, 2) if bankroll > 0 else 0.0
        return default_stake, pct

    pct = min(settings.bet_max_stake_pct, max(0.5, kelly_quarter * 100))
    stake = min(max_stake, bankroll * (pct / 100.0))
    return round(stake, 2), round(pct, 2)


def assess_bet_recommendation(
    *,
    market: str,
    outcome: str,
    ev: float,
    edge_pp: float,
    model_prob: float,
    odd: float,
    bankroll: float = 1000.0,
    kelly_quarter: float = 0.0,
    confidence_score: float = 1.0,
    min_ev_threshold: float | None = None,
    use_kelly: bool | None = None,
) -> BetDecision:
    """Filtra recomendações: bloqueia unknown e EV abaixo do limiar."""
    threshold = (
        settings.ev_recommendation_min_threshold
        if min_ev_threshold is None
        else min_ev_threshold
    )

    log_ev_calculated(market=market, outcome=outcome, ev=ev, edge_pp=edge_pp, odd=odd)

    if is_blocked_market(market):
        log_recommendation_blocked(reason="unknown_market", market=market, ev=ev)
        return BetDecision(
            allowed=False,
            classification="avoid",
            reason="mercado_desconhecido",
        )

    if ev <= 0:
        log_recommendation_blocked(
            reason="negative_ev",
            market=market,
            ev=ev,
            threshold=0.0,
        )
        return BetDecision(
            allowed=False,
            classification="avoid",
            reason="ev_negativo",
        )

    if ev <= threshold:
        log_recommendation_blocked(
            reason="below_threshold",
            market=market,
            ev=ev,
            threshold=threshold,
        )
        return BetDecision(
            allowed=False,
            classification="avoid",
            reason="ev_abaixo_limiar",
        )

    classification = classify_recommendation(
        ev=ev,
        edge_pp=edge_pp,
        model_prob=model_prob,
        confidence_score=confidence_score,
        threshold=threshold,
    )
    if classification == "avoid":
        log_recommendation_blocked(
            reason="below_threshold",
            market=market,
            ev=ev,
            threshold=threshold,
        )
        return BetDecision(
            allowed=False,
            classification="avoid",
            reason="classificacao_evitar",
        )

    stake_brl, stake_pct = compute_conservative_stake(
        bankroll=bankroll,
        kelly_quarter=kelly_quarter,
        classification=classification,
        use_kelly=use_kelly,
    )

    log_recommendation_allowed(
        market=market,
        classification=classification,
        ev=ev,
        stake_brl=stake_brl,
    )

    return BetDecision(
        allowed=True,
        classification=classification,
        suggested_stake_brl=stake_brl,
        suggested_stake_pct=stake_pct,
        use_kelly=bool(use_kelly if use_kelly is not None else settings.bet_use_fractional_kelly),
    )


def filter_recommendations(
    candidates: list[dict[str, Any]],
    *,
    bankroll: float = 1000.0,
    confidence_score: float = 1.0,
    min_ev_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """Filtra lista de dicts de recomendação já montados."""
    out: list[dict[str, Any]] = []
    for item in candidates:
        decision = assess_bet_recommendation(
            market=str(item.get("market", "")),
            outcome=str(item.get("outcome", "")),
            ev=float(item.get("expected_value") or item.get("ev") or 0),
            edge_pp=float(item.get("edge_pp") or 0),
            model_prob=float(item.get("model_prob") or 0),
            odd=float(item.get("market_odd") or item.get("odd") or 0),
            bankroll=bankroll,
            kelly_quarter=float(item.get("kelly_quarter") or 0),
            confidence_score=confidence_score,
            min_ev_threshold=min_ev_threshold,
        )
        if not decision.allowed:
            continue
        enriched = dict(item)
        enriched["classification"] = decision.classification
        enriched["suggested_stake_brl"] = decision.suggested_stake_brl
        enriched["suggested_stake_pct"] = decision.suggested_stake_pct
        out.append(enriched)
    return out


def aporte_to_dict(aporte: Any) -> dict[str, Any]:
    from dataclasses import asdict, is_dataclass

    if is_dataclass(aporte):
        return asdict(aporte)
    if isinstance(aporte, dict):
        return dict(aporte)
    return {}
