import argparse
import asyncio

import structlog

from ingest.fixtures.brasileirao import import_seasons as import_brasileirao
from ingest.fixtures.brasileirao_serie_b import import_seasons as import_serie_b
from ingest.fixtures.copa_brasil import import_seasons as import_copa
from ingest.fixtures.libertadores import import_seasons as import_libertadores
from ingest.fixtures.store import load_fixtures

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)

IMPORTERS = {
    "brasileirao": import_brasileirao,
    "serie_b": import_serie_b,
    "copa": import_copa,
    "libertadores": import_libertadores,
}


async def _import_competition(name: str, seasons: list[int]) -> None:
    importer = IMPORTERS[name]
    df = await importer(seasons)
    if df.empty:
        print(f"{name}: nenhum jogo importado.")
        return
    labeled = int(df["label"].notna().sum())
    print(
        f"{name}: {len(df)} jogos ({labeled} com label) | "
        f"1={ (df['label']=='1').sum() } X={ (df['label']=='X').sum() } 2={ (df['label']=='2').sum() }"
    )


async def run(competitions: list[str], seasons: list[int]) -> None:
    targets = list(IMPORTERS.keys()) if "all" in competitions else competitions
    for comp in targets:
        await _import_competition(comp, seasons)

    stored = load_fixtures()
    if not stored.empty:
        by_comp = stored.groupby("competition").size().to_dict()
        print(f"Total no lake: {len(stored)} jogos — {by_comp}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa resultados históricos (openfootball) para labels"
    )
    parser.add_argument(
        "--competition",
        choices=["brasileirao", "serie_b", "copa", "libertadores", "all"],
        default="all",
        help="Competição a importar",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2022, 2023, 2024, 2025],
        help="Temporadas (Copa/Libertadores: só anos com arquivo no repositório)",
    )
    args = parser.parse_args()
    asyncio.run(run([args.competition], args.seasons))


if __name__ == "__main__":
    main()
