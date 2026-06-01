import asyncio
import argparse

import structlog

from ingest.sources import collect_all_sources
from ingest.sources_loader import load_sources
from ingest.storage import save_bronze

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(fetch_body: bool) -> None:
    articles = await collect_all_sources(fetch_full_body=fetch_body)
    path = save_bronze(articles)
    print(f"Coletados {len(articles)} artigos. Salvo em: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta notícias esportivas via RSS")
    parser.add_argument(
        "--fetch-body",
        action="store_true",
        help="Busca corpo completo de cada artigo (mais lento)",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Lista fontes configuradas em data/sources.yaml",
    )
    args = parser.parse_args()

    if args.list_sources:
        for src in load_sources():
            print(f"  {src.source:<20} {src.name:<22} {src.feed_url}")
        return

    asyncio.run(run(fetch_body=args.fetch_body))


if __name__ == "__main__":
    main()
