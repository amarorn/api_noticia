import argparse

import structlog

from ingest.gcp.sync import sync_all_layers, sync_layer

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Envia Parquet local para GCS e carrega no BigQuery"
    )
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "gold", "fixtures", "sofascore", "all"],
        default="all",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Substitui tabela no BigQuery (WRITE_TRUNCATE)",
    )
    args = parser.parse_args()
    disposition = "WRITE_TRUNCATE" if args.truncate else "WRITE_APPEND"

    if args.layer == "all":
        results = sync_all_layers()
    else:
        results = [sync_layer(args.layer, write_disposition=disposition)]

    for r in results:
        print(f"{r['layer']}: {r['files']} arquivo(s) → {r['table']}")


if __name__ == "__main__":
    main()
