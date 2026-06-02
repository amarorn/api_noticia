import argparse
import asyncio

import structlog

from ingest.fixtures.world_cup import (
    DEFAULT_WC_SEASONS,
    WC_EDITIONS,
    import_wc_seasons,
    list_wc_seasons,
    load_wc_fixtures,
)

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

    labeled = int(df["label"].notna().sum())
    print(f"Importados {len(df)} jogos ({labeled} com label) | Copas: {min(seasons)}–{max(seasons)}")
    print(
        f"Distribuição: 1={ (df['label']=='1').sum() }, "
        f"X={ (df['label']=='X').sum() }, 2={ (df['label']=='2').sum() }"
    )
    if "phase" in df.columns:
        print(f"Fases: {df['phase'].value_counts().to_dict()}")

    by_season = df.groupby("season").size().sort_index()
    print("\nJogos por edição:")
    for season, count in by_season.items():
        print(f"  {season}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa resultados da Copa do Mundo (openfootball, 1930–2022)"
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        help="Anos específicos (ex: 1994 2014 2022)",
    )
    parser.add_argument(
        "--last",
        type=int,
        default=20,
        help="Importar as últimas N Copas concluídas (default: 20)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=f"Todas as {len(WC_EDITIONS)} edições disponíveis (1930–2022)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista edições disponíveis e sai",
    )
    args = parser.parse_args()

    if args.list:
        print(f"Edições openfootball ({len(WC_EDITIONS)}):")
        for year in sorted(WC_EDITIONS):
            print(f"  {year} → {WC_EDITIONS[year]}")
        print(f"\nDefault (--last {args.last}): {list_wc_seasons(last_n=args.last)}")
        return

    if args.seasons:
        seasons = args.seasons
    elif args.all:
        seasons = list_wc_seasons(include_all=True)
    else:
        seasons = list_wc_seasons(last_n=args.last)

    invalid = [s for s in seasons if s not in WC_EDITIONS]
    if invalid:
        print(f"Edições inválidas: {invalid}. Use --list para ver opções.")
        return

    asyncio.run(run(seasons))

    stored = load_wc_fixtures()
    if not stored.empty:
        from config import settings

        count = len(list(settings.fixtures_path.glob("world_cup_*.parquet")))
        print(f"\nTotal no lake: {len(stored)} jogos em {count} arquivo(s) world_cup_*.parquet")


if __name__ == "__main__":
    main()
