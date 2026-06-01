import asyncio
import argparse

import structlog

from ingest.meta import collection_stats, log_collection
from ingest.sources import collect_all_sources
from ingest.storage import save_bronze
from pipelines.silver import run_silver_pipeline

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(fetch_body: bool, pipeline: bool) -> None:
    articles = await collect_all_sources(fetch_full_body=fetch_body)
    save_bronze(articles)

    by_source: dict[str, int] = {}
    for a in articles:
        by_source[a.source] = by_source.get(a.source, 0) + 1
    log_collection(len(articles), by_source, stage="bronze")

    print(f"Coletados {len(articles)} artigos.")
    for src, count in sorted(by_source.items()):
        print(f"  {src}: {count}")

    if pipeline:
        path = run_silver_pipeline()
        log_collection(len(articles), by_source, stage="silver")
        print(f"Silver atualizado: {path or 'sem dados'}")

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
