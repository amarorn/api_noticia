"""Bronze Superbet → DataFrame para BigQuery."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from config import settings


def load_bronze_superbet_events() -> pd.DataFrame:
    base = settings.bronze_path / "superbet" / "events"
    rows: list[dict] = []
    if not base.exists():
        return pd.DataFrame()

    for event_dir in sorted(base.iterdir()):
        if not event_dir.is_dir():
            continue
        for path in sorted(event_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            inplay = payload.get("inplay") or {}
            rows.append(
                {
                    "event_id": payload.get("event_id"),
                    "home_team": payload.get("home_team"),
                    "away_team": payload.get("away_team"),
                    "event_name": payload.get("event_name"),
                    "utc_date": payload.get("utc_date"),
                    "betradar_id": payload.get("betradar_id"),
                    "is_live": payload.get("is_live"),
                    "home_score": inplay.get("home_score"),
                    "away_score": inplay.get("away_score"),
                    "minute": inplay.get("minute"),
                    "home_corners": inplay.get("home_corners"),
                    "away_corners": inplay.get("away_corners"),
                    "h2h_odds": json.dumps(payload.get("h2h_odds") or {}, ensure_ascii=False),
                    "h2h_implied": json.dumps(payload.get("h2h_implied") or {}, ensure_ascii=False),
                    "raw_market_count": payload.get("raw_market_count"),
                    "captured_at": payload.get("captured_at"),
                    "source_file": str(path.relative_to(settings.bronze_path)),
                }
            )

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "utc_date" in df.columns:
        df["utc_date"] = pd.to_datetime(df["utc_date"], utc=True, errors="coerce")
    if "captured_at" in df.columns:
        df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True, errors="coerce")
    return df.drop_duplicates(subset=["event_id", "captured_at"], keep="last")
