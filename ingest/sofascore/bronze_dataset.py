from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.sofascore.compact_stats import JSON_SUFFIX

logger = structlog.get_logger()


def load_bronze_sofascore_events(*, stats_dir: Path | None = None) -> pd.DataFrame:
    root = stats_dir or settings.sofascore_stats_dir
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob(f"*{JSON_SUFFIX}")):
        try:
            raw_text = path.read_text(encoding="utf-8")
            payload = json.loads(raw_text)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("bronze_sofascore_skip", path=str(path), error=str(exc))
            continue
        if not isinstance(payload, dict) or payload.get("event_id") is None:
            continue
        rows.append(
            {
                "event_id": int(payload["event_id"]),
                "home_team": payload.get("home_team"),
                "away_team": payload.get("away_team"),
                "match_date": payload.get("match_date"),
                "source": payload.get("source", "sofascore"),
                "fetched_at": payload.get("fetched_at"),
                "json_filename": path.name,
                "payload_json": raw_text,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "event_id",
                "home_team",
                "away_team",
                "match_date",
                "source",
                "fetched_at",
                "json_filename",
                "payload_json",
                "ingested_at",
            ]
        )
    df = pd.DataFrame(rows)
    df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
    return df.drop_duplicates(subset=["event_id"], keep="last").reset_index(drop=True)
