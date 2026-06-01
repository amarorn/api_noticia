import argparse
import json
from pathlib import Path

from ingest.odds.the_odds_api import fetch_live_h2h_odds, merge_schedule_with_odds, save_odds_file

DEFAULT_SCHEDULE_FILE = Path("data/rounds/wc_2026.json")
DEFAULT_OUTPUT_FILE = Path("data/rounds/wc_2026_odds.json")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Busca odds reais da Copa e salva em JSON")
    parser.add_argument(
        "--schedule-file",
        type=Path,
        default=DEFAULT_SCHEDULE_FILE,
        help="Arquivo com jogos da rodada (home_team/away_team)",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=DEFAULT_OUTPUT_FILE,
        help="Arquivo de saída com odds reais",
    )
    parser.add_argument(
        "--sport-key",
        type=str,
        default=None,
        help="Sport key da Odds API (padrão: soccer_fifa_world_cup)",
    )
    parser.add_argument(
        "--bookmaker",
        type=str,
        default=None,
        help="Bookmaker key opcional (ex: bet365)",
    )
    parser.add_argument(
        "--regions",
        type=str,
        default=None,
        help="Regiões da Odds API (ex: eu,uk,us)",
    )
    parser.add_argument("--json", action="store_true", help="Imprimir conteúdo final em JSON")
    args = parser.parse_args()

    schedule = _load_json(args.schedule_file)
    try:
        live_odds = fetch_live_h2h_odds(
            sport_key=args.sport_key,
            regions=args.regions,
            preferred_bookmaker=args.bookmaker,
        )
    except ValueError as exc:
        raise SystemExit(f"Erro de configuração: {exc}") from exc
    merged, matched = merge_schedule_with_odds(schedule, live_odds)
    out = save_odds_file(merged, args.output_file)

    total = len(schedule.get("matches", []))
    print(f"Odds reais salvas em: {out}")
    print(f"Jogos casados com odds: {matched}/{total}")
    if matched == 0:
        print("Nenhum jogo da rodada foi encontrado no feed ao vivo.")
    if args.json:
        print(json.dumps(merged, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
