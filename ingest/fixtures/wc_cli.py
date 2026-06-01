import argparse
import asyncio

import structlog

from ingest.fixtures.world_cup import DEFAULT_WC_SEASONS, import_wc_seasons, load_wc_fixtures

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(seasons: list[int]) -> None:
    df = await import_wc_seasons(seasons)
    if df.empty:
        print("Nenhum jogo importado.")
        return

    labeled = df["label"].notna().sum()
    print(f"Importados {len(df)} jogos ({labeled} com label) das Copas {seasons}")
    print(
        f"Distribuição: 1={ (df['label']=='1').sum() }, "
        f"X={ (df['label']=='X').sum() }, 2={ (df['label']=='2').sum() }"
    )
    if "phase" in df.columns:
        print(f"Fases: {df['phase'].value_counts().to_dict()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa resultados da Copa do Mundo (openfootball)")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=DEFAULT_WC_SEASONS,
        help="Anos das Copas (ex: 1994 2014 2022)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.seasons))

    stored = load_wc_fixtures()
    if not stored.empty:
        from config import settings

        count = len(list(settings.fixtures_path.glob("world_cup_*.parquet")))
        print(f"Total no lake: {len(stored)} jogos em {count} arquivo(s)")


if __name__ == "__main__":
    main()
