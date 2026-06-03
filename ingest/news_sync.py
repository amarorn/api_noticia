import asyncio
from datetime import datetime, timezone

import pandas as pd

from ingest.meta import log_collection
from ingest.sources import collect_all_sources
from ingest.storage import save_bronze
from pipelines.silver import bronze_to_silver, load_silver, run_silver_pipeline, save_silver

_sync_lock = asyncio.Lock()


def _incremental_silver_from_bronze(articles: list) -> str | None:
    df = pd.DataFrame([a.model_dump(mode="json") for a in articles])
    silver_batch = bronze_to_silver(df)
    path = save_silver(silver_batch)
    return str(path) if path else None


async def sync_news_sources(
    *,
    fetch_body: bool = False,
    run_silver: bool = True,
    full_silver_rebuild: bool = False,
) -> dict:
    async with _sync_lock:
        return await _sync_news_sources_impl(
            fetch_body=fetch_body,
            run_silver=run_silver,
            full_silver_rebuild=full_silver_rebuild,
        )


async def _sync_news_sources_impl(
    *,
    fetch_body: bool,
    run_silver: bool,
    full_silver_rebuild: bool,
) -> dict:
    articles = await collect_all_sources(fetch_full_body=fetch_body)
    await asyncio.to_thread(save_bronze, articles)

    by_source: dict[str, int] = {}
    for article in articles:
        by_source[article.source] = by_source.get(article.source, 0) + 1

    log_collection(len(articles), by_source, stage="bronze")

    silver_path: str | None = None
    if run_silver:
        if full_silver_rebuild:
            path = await asyncio.to_thread(run_silver_pipeline)
            silver_path = str(path) if path else None
        elif articles:
            silver_path = await asyncio.to_thread(_incremental_silver_from_bronze, articles)
        log_collection(len(articles), by_source, stage="silver")

    silver_df = await asyncio.to_thread(load_silver)

    return {
        "collected": len(articles),
        "by_source": by_source,
        "silver_updated": run_silver,
        "silver_path": silver_path,
        "articles_silver": len(silver_df),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
