from dataclasses import dataclass
from pathlib import Path

import structlog
import yaml

from config import settings

logger = structlog.get_logger()


@dataclass(frozen=True)
class RSSSourceConfig:
    source: str
    feed_url: str
    name: str


def load_sources(path: Path | None = None) -> list[RSSSourceConfig]:
    config_path = path or settings.sources_yaml
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de fontes não encontrado: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    entries = raw.get("sources", [])
    sources: list[RSSSourceConfig] = []
    seen_ids: set[str] = set()

    for entry in entries:
        if entry.get("enabled", True) is False:
            continue

        source_id = entry.get("id", "").strip()
        name = entry.get("name", "").strip()
        url = entry.get("url", "").strip()

        if not source_id or not name or not url:
            logger.warning("source_skipped_invalid", entry=entry)
            continue
        if source_id in seen_ids:
            logger.warning("source_skipped_duplicate", id=source_id)
            continue

        seen_ids.add(source_id)
        sources.append(RSSSourceConfig(source=source_id, feed_url=url, name=name))

    logger.info("sources_loaded", count=len(sources), path=str(config_path))
    return sources
