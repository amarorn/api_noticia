"""Funções auxiliares de conversão de resposta compartilhadas entre routers."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from api.schemas import (
    WcGoalFactors,
    WcMatchValueResponse,
    WcModelBreakdown,
    WcMonteCarloBreakdown,
    WcOutcomeValue,
    WcPredictionResponse,
)

if TYPE_CHECKING:
    from models.ev_value import MatchValueReport
    from models.wc_predictor import WcPrediction


def breakdown_to_response(breakdown: dict) -> WcModelBreakdown:
    pf = breakdown.get("poisson_factors")
    mc = breakdown.get("monte_carlo")
    return WcModelBreakdown(
        dixon_coles=breakdown["dixon_coles"],
        logistic=breakdown["logistic"],
        dixon_coles_rho=breakdown.get("dixon_coles_rho"),
        poisson_factors=WcGoalFactors(**pf) if pf else None,
        holdout_2022_accuracy=breakdown.get("holdout_2022_accuracy"),
        ensemble_weights=breakdown["ensemble_weights"],
        ensemble_brier=breakdown.get("ensemble_brier"),
        kxl_baseline=breakdown.get("kxl_baseline"),
        kxl_collision=breakdown.get("kxl_collision"),
        kxl_dynamic=breakdown.get("kxl_dynamic"),
        kxl_fept=breakdown.get("kxl_fept"),
        monte_carlo=WcMonteCarloBreakdown(**mc) if mc else None,
    )


def wc_prediction_to_response(
    pred: "WcPrediction",
    *,
    actual_score: str | None = None,
    actual_outcome: str | None = None,
) -> WcPredictionResponse:
    from models.wc_prediction_meta import build_prediction_metadata

    meta = build_prediction_metadata(
        {"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away},
        pred.prediction,
    )
    prediction_hit = None
    if actual_outcome is not None:
        prediction_hit = pred.prediction == actual_outcome

    return WcPredictionResponse(
        home_team=pred.home_team,
        away_team=pred.away_team,
        prediction=pred.prediction,
        confidence=round(pred.confidence, 4),
        prob_home=round(pred.prob_home, 4),
        prob_draw=round(pred.prob_draw, 4),
        prob_away=round(pred.prob_away, 4),
        poisson_score=pred.poisson_score,
        expected_goals=pred.expected_goals,
        context=pred.context,
        h2h_summary=pred.h2h_summary,
        model_breakdown=breakdown_to_response(pred.model_breakdown),
        max_prob_outcome=meta["max_prob_outcome"],
        max_prob=meta["max_prob"],
        prob_margin=meta["prob_margin"],
        uncertainty=meta["uncertainty"],
        pick_reason=meta["pick_reason"],
        actual_score=actual_score,
        actual_outcome=actual_outcome,
        prediction_hit=prediction_hit,
    )


def match_value_to_response(report: "MatchValueReport") -> WcMatchValueResponse:
    best = None
    if report.best:
        best = WcOutcomeValue(
            outcome=report.best.outcome,
            odd=report.best.odd,
            model_prob=report.best.model_prob,
            implied_prob=report.best.implied_prob,
            expected_value=report.best.expected_value,
            fair_odd=report.best.fair_odd,
            kelly_quarter=report.best.kelly_quarter,
        )
    outcomes = [
        WcOutcomeValue(
            outcome=item.outcome,
            odd=item.odd,
            model_prob=item.model_prob,
            implied_prob=item.implied_prob,
            expected_value=item.expected_value,
            fair_odd=item.fair_odd,
            kelly_quarter=item.kelly_quarter,
        )
        for item in report.outcomes
    ]
    return WcMatchValueResponse(
        home_team=report.home_team,
        away_team=report.away_team,
        best=best,
        outcomes=outcomes,
    )


def sanitize_match_item(data: dict) -> dict:
    out = dict(data)
    group = out.get("group_name")
    if group is None or (isinstance(group, float) and math.isnan(group)):
        out["group_name"] = None
    else:
        out["group_name"] = str(group)
    return out
