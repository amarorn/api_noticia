import json
from pathlib import Path

from config import settings
from models.wc_artifact import (
    fixtures_fingerprint,
    hyperparams_fingerprint,
    squads_fingerprint,
)

_memory: dict[str, dict] = {}
_disk_loaded = False


CACHE_FORMAT_VERSION = 2  # bump quando o formato da resposta mudar

def artifact_fingerprint() -> str:
    return f"{fixtures_fingerprint()}:{squads_fingerprint()}:{hyperparams_fingerprint()}:v{CACHE_FORMAT_VERSION}"


def _cache_file() -> Path:
    return settings.lake_root / "cache" / "wc_round_predictions.json"


def match_key(home: str, away: str, phase: str) -> str:
    return f"{home}|{away}|{phase}"


def invalidate_wc_round_cache() -> None:
    global _disk_loaded
    _memory.clear()
    _disk_loaded = False
    path = _cache_file()
    if path.exists():
        path.unlink()


def _load_disk_if_needed() -> None:
    global _disk_loaded
    if _disk_loaded:
        return
    _disk_loaded = True
    path = _cache_file()
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    if payload.get("artifact_fingerprint") != artifact_fingerprint():
        return
    for key, value in payload.get("predictions", {}).items():
        _memory.setdefault(key, value)


def get_cached(key: str) -> dict | None:
    _load_disk_if_needed()
    return _memory.get(key)


def set_cached(key: str, value: dict) -> None:
    _memory[key] = value


def persist_to_disk() -> None:
    if not _memory:
        return
    path = _cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact_fingerprint": artifact_fingerprint(),
        "predictions": _memory,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def warm_from_disk() -> int:
    _load_disk_if_needed()
    return len(_memory)
