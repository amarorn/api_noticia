import argparse
import asyncio

import structlog

from ingest.fixtures.world_cup import (
    DEFAULT_WC_SEASONS,
    import_wc_seasons,
    list_available_seasons,
    load_wc_fixtures,
    missing_local_seasons,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


async def run(seasons: list[int], *, skip_existing: bool) -> None:
    df = await import_wc_seasons(seasons, skip_existing=skip_existing)
    if df.empty:
        print("Nenhum jogo na base de Copas.")
        return

    seasons_in_base = sorted(int(s) for s in df["season"].unique())
    labeled = int(df["label"].notna().sum())
    print(f"Base atual: {len(df)} jogos em {len(seasons_in_base)} edições ({seasons_in_base[0]}–{seasons_in_base[-1]})")
    print(
        f"Resultados: mandante={int((df['label'] == '1').sum())}, "
        f"empate={int((df['label'] == 'X').sum())}, "
        f"visitante={int((df['label'] == '2').sum())}"
    )
    print(f"Jogos com placar/label: {labeled}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa resultados da Copa do Mundo (openfootball)")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        help=f"Anos das Copas. Padrão: todas ({len(DEFAULT_WC_SEASONS)} edições)",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Importa só edições sem arquivo world_cup_YYYY.parquet no lake",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reimporta mesmo se o parquet da edição já existir",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista edições disponíveis na fonte e no lake local",
    )
    args = parser.parse_args()

    if args.list:
        missing = missing_local_seasons()
        print(f"Fonte openfootball: {len(list_available_seasons())} edições ({DEFAULT_WC_SEASONS[0]}–{DEFAULT_WC_SEASONS[-1]})")
        print(f"Faltando no lake: {missing or 'nenhuma'}")
        stored = load_wc_fixtures()
        if not stored.empty:
            print(f"No lake: {len(stored)} jogos")
        return

    if args.missing_only:
        seasons = missing_local_seasons()
        if not seasons:
            print("Todas as edições já estão no lake.")
            stored = load_wc_fixtures()
            print(f"Total: {len(stored)} jogos")
            return
        print(f"Importando edições faltantes: {seasons}")
    else:
        seasons = args.seasons or DEFAULT_WC_SEASONS

    skip_existing = not args.force
    asyncio.run(run(seasons, skip_existing=skip_existing))

    from config import settings

    files = sorted(settings.fixtures_path.glob("world_cup_*.parquet"))
    stored = load_wc_fixtures()
    print(f"Arquivos no lake: {len(files)} | Total: {len(stored)} jogos")
    print("Reinicie a API (./scripts/dev-api-stable.sh) para recarregar os modelos da Copa.")


if __name__ == "__main__":
    main()
