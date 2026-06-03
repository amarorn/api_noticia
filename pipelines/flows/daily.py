"""
Flow diário: coleta RSS → bronze → silver.

Prefect (opcional): pip install -e ".[orchestration]"
Deploy local: prefect deployment build pipelines/flows/daily.py:daily_news_flow -n daily
"""

from __future__ import annotations

import asyncio

import structlog

from ingest.sources import collect_all_sources
from ingest.storage import save_bronze
from pipelines.silver import run_silver_pipeline

logger = structlog.get_logger()


def _collect_and_silver(fetch_body: bool = False) -> dict:
    articles = asyncio.run(collect_all_sources(fetch_full_body=fetch_body))
    save_bronze(articles)
    silver_path = run_silver_pipeline()
    return {
        "articles": len(articles),
        "silver_path": str(silver_path) if silver_path else None,
    }


try:
    from prefect import flow, task

    @task(name="collect-rss")
    def collect_task(fetch_body: bool = False) -> dict:
        return _collect_and_silver(fetch_body=fetch_body)

    @flow(name="daily-news-pipeline", log_prints=True)
    def daily_news_flow(fetch_body: bool = False) -> dict:
        result = collect_task(fetch_body=fetch_body)
        logger.info("daily_flow_complete", **result)
        return result

except ImportError:

    def daily_news_flow(fetch_body: bool = False) -> dict:
        return _collect_and_silver(fetch_body=fetch_body)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Executa flow diário de notícias")
    parser.add_argument("--fetch-body", action="store_true")
    args = parser.parse_args()
    result = daily_news_flow(fetch_body=args.fetch_body)
    print(result)


if __name__ == "__main__":
    main()
