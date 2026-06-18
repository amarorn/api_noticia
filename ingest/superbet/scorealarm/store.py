"""Persistência bronze ScoreAlarm por evento Superbet."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from config import settings


def scorealarm_bronze_dir(event_id: int) -> Path:
    return settings.bronze_path / "superbet" / "scorealarm" / str(event_id)


def save_scorealarm_snapshot(event_id: int, payload: dict) -> Path:
    base = scorealarm_bronze_dir(event_id)
    base.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    history = base / f"{ts}.json"
    history.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = base / "latest.json"
    latest.write_text(history.read_text(encoding="utf-8"), encoding="utf-8")
    return history


def load_latest_scorealarm_snapshot(event_id: int) -> dict | None:
    path = scorealarm_bronze_dir(event_id) / "latest.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["load_latest_scorealarm_snapshot", "save_scorealarm_snapshot"]
