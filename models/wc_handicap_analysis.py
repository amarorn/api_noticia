"""Monta análise de handicap asiático (modelo × Superbet) para API ao vivo."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from ingest.superbet.parser import SuperbetEventSnapshot
from models.wc_handicap import (
    DEFAULT_HANDICAP_LINES,
    calculate_handicap_ev,
    format_handicap_key,
    kelly_stake,
    recommendation_for_ev,
)

Side = Literal["home", "away"]


def build_handicap_lines(
    *,
    model_probs: dict[str, float],
    book_odds: dict[str, float],
    bankroll: float,
    min_bet_ev: float = 0.05,
) -> list[dict[str, Any]]:
    """Lista linhas home/away com EV, Kelly e recomendação."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Side, float]] = set()

    for line in DEFAULT_HANDICAP_LINES:
        for side in ("home", "away"):
            if side == "home":
                prob_key = format_handicap_key("home", line)
                line_val = line
            else:
                line_val = -line if line != 0 else 0.0
                prob_key = format_handicap_key("away", line_val)
            if (side, line_val) in seen:
                continue
            seen.add((side, line_val))
            model_prob = float(model_probs.get(prob_key, 0.0))
            odd = book_odds.get(prob_key)
            ev = calculate_handicap_ev(model_prob, odd) if odd else -1.0
            rows.append(
                {
                    "line": line_val,
                    "side": side,
                    "model_prob": round(model_prob, 4),
                    "superbet_odd": round(float(odd), 3) if odd else None,
                    "ev": round(ev, 4) if odd else None,
                    "kelly_stake": round(kelly_stake(model_prob, odd, bankroll), 2)
                    if odd and odd > 1.0
                    else 0.0,
                    "recommendation": recommendation_for_ev(ev, min_bet=min_bet_ev)
                    if odd
                    else "avoid",
                }
            )
    rows.sort(key=lambda r: (r["line"], r["side"]))
    return rows


def build_handicap_analysis(
    *,
    event_id: int,
    home_team: str,
    away_team: str,
    current_score: str,
    minute: int,
    model_probs: dict[str, float],
    snapshot: SuperbetEventSnapshot | None,
    bankroll: float = 1000.0,
    phase: str = "group",
) -> dict[str, Any]:
    book_odds = snapshot.handicap_odds if snapshot else {}
    lines = build_handicap_lines(
        model_probs=model_probs,
        book_odds=book_odds,
        bankroll=bankroll,
    )
    bet_candidates = [row for row in lines if row["recommendation"] == "bet"]
    bet_candidates.sort(key=lambda r: float(r.get("ev") or -999), reverse=True)
    best = bet_candidates[0] if bet_candidates else None
    return {
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "current_score": current_score,
        "minute": minute,
        "phase": phase,
        "lines": lines,
        "best_bet": best,
        "model_probs": {k: round(v, 4) for k, v in model_probs.items()},
        "superbet_odds": book_odds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["build_handicap_analysis", "build_handicap_lines"]
