from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from pathlib import Path

import structlog

from config import settings

logger = structlog.get_logger()


def _meta_dir() -> Path:
    path = settings.lake_root / "_meta"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_collection(articles_count: int, sources: dict[str, int], stage: str = "bronze") -> None:
    log_file = _meta_dir() / "collections.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "articles_count": articles_count,
        "sources": sources,
    }
    with log_file.open("a", encoding="utf-8") as f:
        f.write(dumps(entry, ensure_ascii=False) + "\n")
    logger.info("collection_logged", articles=articles_count, stage=stage)


def collection_stats() -> dict:
    log_file = _meta_dir() / "collections.jsonl"
    if not log_file.exists():
        return {"total_runs": 0, "total_articles": 0, "last_run": None}

    runs = 0
    total = 0
    last_run = None
    for line in log_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        import json
        entry = json.loads(line)
        runs += 1
        total += entry.get("articles_count", 0)
        last_run = entry.get("timestamp")

    return {"total_runs": runs, "total_articles": total, "last_run": last_run}
