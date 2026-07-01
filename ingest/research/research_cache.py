"""Cache em disco para relatórios de pesquisa pré-jogo (evita re-cobrar API a cada reload)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from config import settings

_CACHE_DIR = Path(settings.lake_root) / "pregame_research"


def _cache_path(home: str, away: str) -> Path:
    slug = f"{home.lower().replace(' ', '_')}_vs_{away.lower().replace(' ', '_')}"
    return _CACHE_DIR / f"{slug}.json"


def load_cached(home: str, away: str) -> dict | None:
    path = _cache_path(home, away)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age = time.time() - data.get("cached_at", 0)
        if age > settings.pregame_research_cache_ttl_sec:
            return None
        return data
    except Exception:
        return None


def save_cached(home: str, away: str, payload: dict) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(home, away)
    payload["cached_at"] = time.time()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_cached(home: str, away: str) -> bool:
    path = _cache_path(home, away)
    if path.exists():
        path.unlink()
        return True
    return False
