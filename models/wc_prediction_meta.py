"""Metadados de palpite WC (incerteza, margem, acerto vs resultado real)."""
from __future__ import annotations

from typing import Any


def outcome_from_score(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "1"
    if home_score < away_score:
        return "2"
    return "X"


def build_prediction_metadata(
    probs: dict[str, float],
    prediction: str,
) -> dict[str, Any]:
    """Calcula margem, incerteza e outcome de maior probabilidade bruta."""
    p1, px, p2 = probs["1"], probs["X"], probs["2"]
    ordered = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    top_outcome, top_prob = ordered[0]
    second_prob = ordered[1][1]
    margin = top_prob - second_prob

    if margin < 0.08 or top_prob < 0.38:
        uncertainty = "alta"
    elif margin < 0.15 or top_prob < 0.48:
        uncertainty = "media"
    else:
        uncertainty = "baixa"

    pick_reason = "argmax"
    if prediction == "X" and top_outcome != "X":
        pick_reason = "empate_equilibrio"

    return {
        "max_prob_outcome": top_outcome,
        "max_prob": round(top_prob, 4),
        "prob_margin": round(margin, 4),
        "uncertainty": uncertainty,
        "pick_reason": pick_reason,
        "prob_home": round(p1, 4),
        "prob_draw": round(px, 4),
        "prob_away": round(p2, 4),
    }


__all__ = ["build_prediction_metadata", "outcome_from_score"]
