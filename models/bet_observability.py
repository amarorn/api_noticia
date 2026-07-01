"""Observabilidade estruturada para geração de palpites e bloqueios de EV."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_lock = threading.Lock()


@dataclass
class BetObservabilityMetrics:
    predictions_generated: int = 0
    recommendations_allowed: int = 0
    blocked_negative_ev: int = 0
    blocked_unknown_market: int = 0
    blocked_below_threshold: int = 0
    route_errors: int = 0
    api_failures: int = 0
    ev_sum_allowed: float = 0.0
    ev_count_allowed: int = 0
    blocked_by_market: dict[str, int] = field(default_factory=dict)
    roi_by_market: dict[str, float] = field(default_factory=dict)


_metrics = BetObservabilityMetrics()


def get_bet_observability_metrics() -> dict[str, Any]:
    with _lock:
        avg_ev = (
            _metrics.ev_sum_allowed / _metrics.ev_count_allowed
            if _metrics.ev_count_allowed
            else 0.0
        )
        return {
            "predictions_generated": _metrics.predictions_generated,
            "recommendations_allowed": _metrics.recommendations_allowed,
            "blocked_negative_ev": _metrics.blocked_negative_ev,
            "blocked_unknown_market": _metrics.blocked_unknown_market,
            "blocked_below_threshold": _metrics.blocked_below_threshold,
            "route_errors": _metrics.route_errors,
            "api_failures": _metrics.api_failures,
            "avg_ev_recommended": round(avg_ev, 4),
            "blocked_by_market": dict(_metrics.blocked_by_market),
            "roi_by_market": dict(_metrics.roi_by_market),
        }


def reset_bet_observability_metrics() -> None:
    with _lock:
        global _metrics
        _metrics = BetObservabilityMetrics()


def _inc(field: str, amount: int = 1) -> None:
    with _lock:
        setattr(_metrics, field, getattr(_metrics, field) + amount)


def log_prediction_generated(*, home_team: str, away_team: str, source: str) -> None:
    _inc("predictions_generated")
    logger.info(
        "palpite_gerado",
        home_team=home_team,
        away_team=away_team,
        source=source,
    )


def log_ev_calculated(
    *,
    market: str,
    outcome: str,
    ev: float,
    edge_pp: float,
    odd: float,
) -> None:
    logger.debug(
        "ev_calculado",
        market=market,
        outcome=outcome,
        ev=round(ev, 4),
        edge_pp=round(edge_pp, 2),
        odd=odd,
    )


def log_recommendation_blocked(
    *,
    reason: str,
    market: str,
    ev: float | None = None,
    threshold: float | None = None,
) -> None:
    market_key = (market or "unknown").lower()
    with _lock:
        _metrics.blocked_by_market[market_key] = _metrics.blocked_by_market.get(market_key, 0) + 1
        if reason == "unknown_market":
            _metrics.blocked_unknown_market += 1
        elif reason == "negative_ev":
            _metrics.blocked_negative_ev += 1
        elif reason == "below_threshold":
            _metrics.blocked_below_threshold += 1

    logger.info(
        "recomendacao_bloqueada",
        reason=reason,
        market=market,
        ev=ev,
        threshold=threshold,
    )


def log_recommendation_allowed(
    *,
    market: str,
    classification: str,
    ev: float,
    stake_brl: float,
) -> None:
    _inc("recommendations_allowed")
    with _lock:
        _metrics.ev_sum_allowed += ev
        _metrics.ev_count_allowed += 1
    logger.info(
        "recomendacao_aprovada",
        market=market,
        classification=classification,
        ev=round(ev, 4),
        stake_brl=round(stake_brl, 2),
    )


def log_route_error(path: str, detail: str | None = None) -> None:
    _inc("route_errors")
    logger.warning("erro_rota_frontend", path=path, detail=detail)


def log_api_failure(endpoint: str, detail: str) -> None:
    _inc("api_failures")
    logger.warning("falha_api", endpoint=endpoint, detail=detail)


def update_roi_by_market(roi_map: dict[str, float]) -> None:
    with _lock:
        _metrics.roi_by_market = dict(roi_map)
