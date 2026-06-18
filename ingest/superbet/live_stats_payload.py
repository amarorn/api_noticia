"""Monta payload live_stats para advice (Superbet + proxy Sofascore)."""
from __future__ import annotations

from typing import Any

from ingest.superbet.parser import SuperbetEventSnapshot


def possession_from_corners(home_corners: int, away_corners: int) -> tuple[float, float] | None:
    """Proxy de posse quando Sofascore indisponível (35–65% pela razão de escanteios)."""
    total = home_corners + away_corners
    if total <= 0:
        return None
    share = home_corners / total
    home_pct = 35.0 + share * 30.0
    return home_pct, 100.0 - home_pct


def build_live_stats_payload(
    *,
    snapshot: SuperbetEventSnapshot,
    live_stats: dict[str, float | None],
    tick_extra: dict[str, Any],
    sofascore_event_id: int | None,
    sofascore_skipped: str | None = None,
    prob_next_goal_home: float | None = None,
    prob_next_goal_away: float | None = None,
    scorealarm_stats: dict[str, float | None] | None = None,
    scorealarm_stale: bool = False,
) -> dict[str, Any]:
    ip = snapshot.inplay
    sa = scorealarm_stats or {}
    home_corners = int(sa.get("home_corners") or tick_extra.get("home_corners") or 0)
    away_corners = int(sa.get("away_corners") or tick_extra.get("away_corners") or 0)
    home_yellow = int(sa.get("home_yellow_cards") or (ip.home_yellow_cards if ip else 0))
    away_yellow = int(sa.get("away_yellow_cards") or (ip.away_yellow_cards if ip else 0))

    home_poss = sa.get("home_possession_pct")
    away_poss = sa.get("away_possession_pct")
    possession_source: str | None = "scorealarm" if home_poss is not None else None

    if home_poss is None:
        home_poss = live_stats.get("home_possession_pct")
        away_poss = live_stats.get("away_possession_pct")
        possession_source = "sofascore" if home_poss is not None else None

    if home_poss is None:
        proxy = possession_from_corners(home_corners, away_corners)
        if proxy:
            home_poss, away_poss = proxy
            possession_source = "corners_proxy"
        elif prob_next_goal_home is not None and prob_next_goal_away is not None:
            total = prob_next_goal_home + prob_next_goal_away
            if total > 0:
                share = prob_next_goal_home / total
                home_poss = 35.0 + share * 30.0
                away_poss = 100.0 - home_poss
                possession_source = "momentum_proxy"
        else:
            home_poss, away_poss = 50.0, 50.0
            possession_source = "neutral"

    home_shots = sa.get("home_shots_on_target")
    if home_shots is None:
        home_shots = live_stats.get("home_shots_on_target")
    away_shots = sa.get("away_shots_on_target")
    if away_shots is None:
        away_shots = live_stats.get("away_shots_on_target")

    warnings: list[str] = []
    if scorealarm_stale and possession_source == "scorealarm":
        warnings.append("Stats ScoreAlarm em cache (API indisponível).")
    if sofascore_skipped and possession_source != "scorealarm":
        warnings.append(sofascore_skipped)
    elif possession_source == "corners_proxy":
        warnings.append(
            "Posse estimada pela proporção de escanteios (ScoreAlarm/Sofascore indisponíveis)."
        )
    elif possession_source == "momentum_proxy":
        warnings.append(
            "Posse estimada pelo momentum de próximo gol (ScoreAlarm/Sofascore indisponíveis)."
        )

    data_source = "scorealarm" if sa else ("sofascore" if live_stats else "superbet")

    return {
        "source": data_source,
        "possession_source": possession_source,
        "sofascore_event_id": sofascore_event_id,
        "sofascore_available": possession_source == "sofascore",
        "scorealarm_available": possession_source == "scorealarm",
        "scorealarm_stale": scorealarm_stale,
        "home_xg": live_stats.get("home_xg"),
        "away_xg": live_stats.get("away_xg"),
        "home_possession_pct": home_poss,
        "away_possession_pct": away_poss,
        "home_shots_on_target": home_shots,
        "away_shots_on_target": away_shots,
        "home_corners": home_corners,
        "away_corners": away_corners,
        "home_yellow_cards": home_yellow,
        "away_yellow_cards": away_yellow,
        "warnings": warnings,
    }


__all__ = ["build_live_stats_payload", "possession_from_corners"]
