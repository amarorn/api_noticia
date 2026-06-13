"""Alertas quando apostas do usuário divergem do palpite do modelo."""
from __future__ import annotations

from typing import Any

from models.wc_draw_model import resolve_wc_outcome
from models.wc_prediction_meta import build_prediction_metadata


def normalize_h2h_outcome(outcome: str) -> str | None:
    """Normaliza palpite 1/X/2 a partir de variantes home/away/draw."""
    key = (outcome or "").strip().lower()
    if key in {"1", "home"}:
        return "1"
    if key in {"2", "away"}:
        return "2"
    if key in {"x", "draw", "0"}:
        return "X"
    return None


def _outcome_label(outcome: str, home_team: str, away_team: str) -> str:
    if outcome == "1":
        return f"Vitória {home_team}"
    if outcome == "2":
        return f"Vitória {away_team}"
    return "Empate"


def _inplay_h2h_palpite(inplay: dict[str, Any], *, phase: str) -> tuple[str, float, dict[str, float]]:
    probs = {
        "1": float(inplay.get("prob_final_home") or 0),
        "X": float(inplay.get("prob_final_draw") or 0),
        "2": float(inplay.get("prob_final_away") or 0),
    }
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}
    palpite = resolve_wc_outcome(probs, phase=phase)
    return palpite, probs[palpite], probs


def build_against_model_alerts(
    *,
    open_bets: list[dict[str, Any]],
    inplay: dict[str, Any],
    pregame_prediction: str,
    pregame_probs: dict[str, float],
    home_team: str,
    away_team: str,
    phase: str = "friendly",
    user_bet: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Lista alertas para apostas 1X2 contra palpite pré-jogo e/ou in-play."""
    inplay_palpite, inplay_conf, inplay_probs = _inplay_h2h_palpite(inplay, phase=phase)
    pregame_meta = build_prediction_metadata(pregame_probs, pregame_prediction)

    candidates: list[dict[str, Any]] = []
    for bet in open_bets:
        picks = bet.get("picks") or []
        if not picks:
            continue
        pick = picks[0]
        market = str(pick.get("market") or "")
        if market != "h2h":
            continue
        outcome = normalize_h2h_outcome(str(pick.get("outcome") or ""))
        if outcome is None:
            continue
        candidates.append(
            {
                "bet_id": bet.get("id"),
                "market": market,
                "outcome": outcome,
                "stake": float(bet.get("stake") or 0),
                "odds_placed": float(bet.get("odds_placed") or 0),
            }
        )

    if user_bet:
        market = str(user_bet.get("market") or "")
        outcome = normalize_h2h_outcome(str(user_bet.get("outcome") or ""))
        if market == "h2h" and outcome is not None:
            exists = any(
                c["outcome"] == outcome and abs(c["stake"] - float(user_bet.get("stake") or 0)) < 0.01
                for c in candidates
            )
            if not exists:
                candidates.append(
                    {
                        "bet_id": None,
                        "market": market,
                        "outcome": outcome,
                        "stake": float(user_bet.get("stake") or 0),
                        "odds_placed": float(user_bet.get("odds_placed") or 0),
                    }
                )

    alerts: list[dict[str, Any]] = []
    for item in candidates:
        bet_out = item["outcome"]
        vs_pregame = bet_out != pregame_prediction
        vs_inplay = bet_out != inplay_palpite
        if not vs_pregame and not vs_inplay:
            continue

        if vs_pregame and vs_inplay:
            severity = "critical"
        elif vs_inplay:
            severity = "high"
        else:
            severity = "medium"

        bet_label = _outcome_label(bet_out, home_team, away_team)
        pregame_label = _outcome_label(pregame_prediction, home_team, away_team)
        inplay_label = _outcome_label(inplay_palpite, home_team, away_team)

        parts: list[str] = []
        if vs_pregame:
            parts.append(
                f"pré-jogo apontava {pregame_label} ({pregame_probs[pregame_prediction] * 100:.0f}%)"
            )
        if vs_inplay:
            parts.append(
                f"ao vivo o modelo favorece {inplay_label} ({inplay_probs[inplay_palpite] * 100:.0f}%)"
            )

        alerts.append(
            {
                "bet_id": item.get("bet_id"),
                "market": item["market"],
                "bet_outcome": bet_out,
                "bet_outcome_label": bet_label,
                "stake": item["stake"],
                "odds_placed": item.get("odds_placed"),
                "pregame_palpite": pregame_prediction,
                "pregame_prob": round(pregame_probs[pregame_prediction], 4),
                "pregame_uncertainty": pregame_meta["uncertainty"],
                "inplay_palpite": inplay_palpite,
                "inplay_prob": round(inplay_conf, 4),
                "inplay_probs": {
                    k: round(v, 4) for k, v in inplay_probs.items()
                },
                "severity": severity,
                "against_pregame": vs_pregame,
                "against_inplay": vs_inplay,
                "message": (
                    f"Sua aposta ({bet_label}, R$ {item['stake']:.2f}) está contra o modelo: "
                    + " · ".join(parts)
                    + "."
                ),
            }
        )

    order = {"critical": 0, "high": 1, "medium": 2}
    alerts.sort(key=lambda a: order.get(a["severity"], 9))
    return alerts


__all__ = [
    "build_against_model_alerts",
    "normalize_h2h_outcome",
]
