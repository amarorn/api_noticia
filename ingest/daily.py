import asyncio
import argparse

import structlog

from ingest.meta import collection_stats
from ingest.news_sync import sync_news_sources

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(fetch_body: bool, pipeline: bool) -> None:
    result = await sync_news_sources(
        fetch_body=fetch_body,
        run_silver=pipeline,
        full_silver_rebuild=pipeline,
    )

    print(f"Coletados {result['collected']} artigos.")
    for src, count in sorted(result["by_source"].items()):
        print(f"  {src}: {count}")

    if pipeline:
        print(f"Silver atualizado: {result['silver_path'] or 'sem dados'}")

    stats = collection_stats()
    print(f"Total de coletas: {stats['total_runs']} | Artigos acumulados (log): {stats['total_articles']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta diária de notícias + pipeline silver")
    parser.add_argument("--fetch-body", action="store_true", help="Busca corpo completo dos artigos")
    parser.add_argument("--no-pipeline", action="store_true", help="Só bronze, sem silver")
    args = parser.parse_args()
    asyncio.run(run(fetch_body=args.fetch_body, pipeline=not args.no_pipeline))


if __name__ == "__main__":
    main()
