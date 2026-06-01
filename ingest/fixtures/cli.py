import argparse
import asyncio

import structlog

from ingest.fixtures.brasileirao import import_seasons, load_fixtures

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(seasons: list[int]) -> None:
    df = await import_seasons(seasons)
    if df.empty:
        print("Nenhum jogo importado.")
        return

    labeled = df["label"].notna().sum()
    print(f"Importados {len(df)} jogos ({labeled} com label) das temporadas {seasons}")
    print(f"Distribuição: 1={ (df['label']=='1').sum() }, X={ (df['label']=='X').sum() }, 2={ (df['label']=='2').sum() }")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa resultados do Brasileirão (openfootball)")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2022, 2023, 2024],
        help="Temporadas a importar (ex: 2022 2023 2024)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.seasons))

    stored = load_fixtures()
    if not stored.empty:
        print(f"Total no lake: {len(stored)} jogos em {settings_fixtures_count()} arquivo(s)")


def settings_fixtures_count() -> int:
    from config import settings

    return len(list(settings.fixtures_path.glob("brasileirao_*.parquet")))


if __name__ == "__main__":
    main()
