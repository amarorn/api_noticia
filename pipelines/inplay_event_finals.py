"""Placares finais de eventos Superbet (bronze/events)."""
from __future__ import annotations

import json
from pathlib import Path

from config import settings


def find_event_final_score(event_id: int) -> dict | None:
    """Último snapshot bronze do evento com placar final."""
    events_dir = settings.bronze_path / "superbet" / "events" / str(event_id)
    if not events_dir.exists():
        return None
    snapshots = sorted(events_dir.glob("*.json"), key=lambda p: p.stem)
    if not snapshots:
        return None
    try:
        data = json.loads(snapshots[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    inplay = data.get("inplay_stats") or data.get("inplay") or {}
    home_score = inplay.get("home_team_score", inplay.get("home_score"))
    away_score = inplay.get("away_team_score", inplay.get("away_score"))
    try:
        hs = int(home_score)
        aw = int(away_score)
    except (TypeError, ValueError):
        return None
    if hs < 0 or aw < 0:
        return None

    status = (data.get("inplay_stats_metadata") or {}).get("status", "")
    return {
        "event_id": int(event_id),
        "home_team": data.get("home_team"),
        "away_team": data.get("away_team"),
        "home_score_final": hs,
        "away_score_final": aw,
        "status": status,
    }


def load_all_event_final_scores(events_root: Path | None = None) -> dict[int, dict]:
    """Mapa event_id → placar final a partir de pastas bronze/superbet/events."""
    root = events_root or (settings.bronze_path / "superbet" / "events")
    if not root.exists():
        return {}
    out: dict[int, dict] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        try:
            event_id = int(child.name)
        except ValueError:
            continue
        final = find_event_final_score(event_id)
        if final:
            out[event_id] = final
    return out


__all__ = ["find_event_final_score", "load_all_event_final_scores"]
