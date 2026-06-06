from __future__ import annotations

import argparse
import json

from pipelines.lake_query import lake_summary, query_lake, team_sofascore_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consultas SQL locais sobre o datalake (DuckDB + Parquet)"
    )
    parser.add_argument(
        "--preset",
        choices=["summary", "team-xg"],
        help="Consulta pronta (alternativa a --sql)",
    )
    parser.add_argument("--team", type=str, help="Seleção para --preset team-xg")
    parser.add_argument("--limit", type=int, default=5, help="Limite de linhas em team-xg")
    parser.add_argument("--sql", type=str, help="SQL DuckDB (views: bronze, silver, gold, fixtures, sofascore)")
    parser.add_argument("--json", action="store_true", help="Saída JSON")
    args = parser.parse_args()

    if args.preset == "summary":
        result = lake_summary()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for layer, info in result["layers"].items():
                if info["available"]:
                    print(f"{layer}: {info['rows']} linhas")
                else:
                    print(f"{layer}: (sem dados)")
        return

    if args.preset == "team-xg":
        if not args.team:
            parser.error("--preset team-xg requer --team")
        df = team_sofascore_summary(args.team, limit=args.limit)
        if args.json:
            print(df.to_json(orient="records", force_ascii=False, indent=2))
        elif df.empty:
            print(f"Nenhum jogo Sofascore para {args.team}")
        else:
            print(df.to_string(index=False))
        return

    if not args.sql:
        parser.error("Informe --sql ou --preset")

    df = query_lake(args.sql)
    if args.json:
        print(df.to_json(orient="records", force_ascii=False, indent=2))
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
