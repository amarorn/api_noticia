"""Métricas de primeiro tempo extraídas da timeline de incidentes Sofascore."""
from __future__ import annotations

from typing import Any


def _safe_minute(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def map_half_time_metrics(payload: dict[str, Any]) -> dict[str, int]:
    """Conta gols e cartões amarelos até o minuto 45 (inclusive)."""
    out = {
        "ht_goals_home": 0,
        "ht_goals_away": 0,
        "ht_yellow_cards_home": 0,
        "ht_yellow_cards_away": 0,
    }
    for item in payload.get("incidents") or []:
        minute = _safe_minute(item.get("time"))
        if minute is None or minute > 45:
            continue
        is_home = bool(item.get("isHome"))
        side = "home" if is_home else "away"
        incident_type = str(item.get("incidentType") or "").lower()
        incident_class = str(item.get("incidentClass") or "").lower()

        if incident_type == "goal":
            out[f"ht_goals_{side}"] += 1
        elif incident_type == "card" and incident_class != "red":
            out[f"ht_yellow_cards_{side}"] += 1
    return out
