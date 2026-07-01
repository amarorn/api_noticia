"""Persistência de contextos de análise pré-jogo por event_id.

Salva e carrega JSONs em data/live_contexts/{event_id}.json.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

_CONTEXTS_DIR = Path(settings.lake_root) / "live_contexts"


def _context_path(event_id: int) -> Path:
    return _CONTEXTS_DIR / f"{event_id}.json"


def save_match_context(event_id: int, data: dict[str, Any]) -> Path:
    _CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _context_path(event_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("match_context_saved event_id=%s path=%s", event_id, path)
    return path


def load_match_context(event_id: int) -> dict[str, Any] | None:
    path = _context_path(event_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("match_context_load_error event_id=%s: %s", event_id, exc)
        return None


def delete_match_context(event_id: int) -> bool:
    path = _context_path(event_id)
    if path.exists():
        path.unlink()
        return True
    return False


def _teams_slug(home: str, away: str) -> str:
    import re
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "_", s.lower().strip())
    return f"{_norm(home)}-vs-{_norm(away)}"


def save_match_context_by_teams(home: str, away: str, data: dict[str, Any]) -> Path:
    _CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _teams_slug(home, away)
    path = _CONTEXTS_DIR / f"pregame_{slug}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("match_context_by_teams_saved home=%s away=%s path=%s", home, away, path)
    return path


def load_match_context_by_teams(home: str, away: str) -> dict[str, Any] | None:
    slug = _teams_slug(home, away)
    path = _CONTEXTS_DIR / f"pregame_{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("match_context_by_teams_load_error home=%s away=%s: %s", home, away, exc)
        return None


def list_match_contexts() -> list[dict[str, Any]]:
    if not _CONTEXTS_DIR.exists():
        return []
    result = []
    for p in sorted(_CONTEXTS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            result.append({"event_id": int(p.stem), **data})
        except Exception:
            pass
    return result
