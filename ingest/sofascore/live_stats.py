"""Estatísticas ao vivo Sofascore (xG, posse) para ticks in-play."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def fetch_live_match_stats(sofascore_event_id: int) -> dict[str, float | None]:
    """Busca xG e métricas principais de um evento ao vivo.

    Falha silenciosa — não bloqueia o fluxo de advice.
    """
    try:
        from ingest.sofascore.client import SofascoreClient
        from ingest.sofascore.stats_mapper import map_event_statistics

        client = SofascoreClient()
        payload = client.event_statistics(sofascore_event_id)
        mapped = map_event_statistics(payload)
        return {
            "home_xg": _as_float(mapped.get("home_xg")),
            "away_xg": _as_float(mapped.get("away_xg")),
            "home_possession_pct": _as_float(mapped.get("home_possession_pct")),
            "away_possession_pct": _as_float(mapped.get("away_possession_pct")),
            "home_shots_on_target": _as_float(mapped.get("home_shots_on_target")),
            "away_shots_on_target": _as_float(mapped.get("away_shots_on_target")),
        }
    except Exception as exc:
        logger.warning(
            "sofascore_live_stats_falha event_id=%s error=%s",
            sofascore_event_id,
            exc,
        )
        return {}


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["fetch_live_match_stats"]
