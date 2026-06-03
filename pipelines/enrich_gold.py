"""Enriquece camada gold com estatísticas da API-Football (opcional)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
import structlog

from config import settings
from ingest.stats.api_football import ApiFootballClient, summarize_fixture_stats
from models.dataset import load_gold_dataset

logger = structlog.get_logger()


async def enrich_row(client: ApiFootballClient, row: dict) -> dict:
    match_date = pd.to_datetime(row["match_date"], utc=True)
    fixture_id = await client.find_fixture_id(
        row["home_team"],
        row["away_team"],
        match_date.to_pydatetime(),
        season=row.get("season"),
    )
    if not fixture_id:
        return row

    stats = await client.get_fixture_statistics(fixture_id)
    if not stats:
        return row

    extra = summarize_fixture_stats(stats)
    features = row.get("features") or {}
    if isinstance(features, dict):
        features = {**features, **extra}
        row["features"] = features
    return row


async def enrich_gold(limit: int | None = None) -> Path | None:
    df = load_gold_dataset()
    if df.empty:
        logger.warning("enrich_gold_empty")
        return None

    client = ApiFootballClient()
    records = df.to_dict(orient="records")
    if limit:
        records = records[:limit]

    enriched = []
    for row in records:
        try:
            enriched.append(await enrich_row(client, row))
        except Exception as exc:
            logger.warning("enrich_row_failed", match_id=row.get("match_id"), error=str(exc))
            enriched.append(row)

    out_df = pd.DataFrame(enriched)
    settings.gold_path.mkdir(parents=True, exist_ok=True)
    out_path = settings.gold_path / "enriched_api_football.parquet"
    out_df.to_parquet(out_path, index=False)
    logger.info("gold_enriched", path=str(out_path), rows=len(out_df))
    return out_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Enriquece gold com API-Football")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    path = asyncio.run(enrich_gold(limit=args.limit))
    print(f"Enriquecido: {path or 'sem dados'}")


if __name__ == "__main__":
    main()
