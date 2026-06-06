import argparse

import structlog

from ingest.gcp.medallion import LAYER_ALIASES, MEDALLION_TABLES, SYNC_LAYER_ORDER
from ingest.gcp.sync import sync_all_layers, sync_layer

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

_LAYER_CHOICES = sorted(set(SYNC_LAYER_ORDER) | set(LAYER_ALIASES.keys()) | {"all"})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync medallion lake → BigQuery (dataset sports_news_lake)"
    )
    parser.add_argument(
        "--layer",
        choices=_LAYER_CHOICES,
        default="all",
        help=(
            "Camada medalhão: bronze, bronze_sofascore, silver, silver_sofascore, "
            "silver_sofascore_enrich, silver_fixtures, gold, gold_wc "
            "(aliases: sofascore, sofascore_enrich, fixtures)"
        ),
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Substitui tabela no BigQuery (WRITE_TRUNCATE)",
    )
    parser.add_argument(
        "--list-layers",
        action="store_true",
        help="Lista camadas e tabelas BQ",
    )
    args = parser.parse_args()

    if args.list_layers:
        for layer in SYNC_LAYER_ORDER:
            print(f"{layer:20} → {MEDALLION_TABLES[layer]}")
        if LAYER_ALIASES:
            print("\nAliases:")
            for alias, target in sorted(LAYER_ALIASES.items()):
                print(f"  {alias} → {target}")
        return

    disposition = "WRITE_TRUNCATE" if args.truncate else "WRITE_APPEND"

    if args.layer == "all":
        results = sync_all_layers(write_disposition=disposition)
    else:
        results = [sync_layer(args.layer, write_disposition=disposition)]

    for r in results:
        mode = r.get("mode", "gcs")
        rows = r.get("rows")
        extra = f", {rows} linhas" if rows is not None else ""
        print(f"{r['layer']}: {r['files']} arquivo(s) → {r['table']} ({mode}{extra})")


if __name__ == "__main__":
    main()
