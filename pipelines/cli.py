import argparse

import structlog

from ingest.fixtures.brasileirao import load_fixtures
from models.dataset import export_jsonl
from pipelines.gold import run_gold_pipeline
from pipelines.silver import run_silver_pipeline

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Executa pipeline silver → gold")
    parser.add_argument(
        "stage",
        choices=["silver", "gold", "all", "export"],
        help="Estágio do pipeline",
    )
    parser.add_argument("--season", type=int, help="Temporada do Brasileirão (ex: 2024)")
    parser.add_argument("--round", type=int, help="Rodada específica")
    args = parser.parse_args()

    if args.stage in ("silver", "all"):
        path = run_silver_pipeline()
        print(f"Silver: {path or 'sem dados'}")

    if args.stage in ("gold", "all"):
        fixtures = load_fixtures(season=args.season)
        if fixtures.empty:
            print("Gold: sem fixtures. Execute primeiro: import-brasileirao")
        else:
            path = run_gold_pipeline(season=args.season, round_number=args.round)
            labeled = fixtures["label"].notna().sum() if args.round is None else len(fixtures)
            print(f"Gold: {path or 'sem dados'} ({labeled} jogos com label)")

    if args.stage == "export":
        from pathlib import Path

        output = Path("data/training/bolao_train.jsonl")
        count = export_jsonl(output)
        print(f"Exportados {count} exemplos para treino em {output}")


if __name__ == "__main__":
    main()
