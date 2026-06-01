import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd
import structlog

from config import settings
from ingest.fixtures.brasileirao import load_fixtures
from models.baseline import predict_baseline
from pipelines.gold import build_gold_for_match, save_gold
from pipelines.silver import load_silver

logger = structlog.get_logger()

ROUNDS_DIR = Path("data/rounds")


def _make_match_id(home: str, away: str, round_number: int) -> str:
    key = f"live|{round_number}|{home}|{away}"
    return sha256(key.encode()).hexdigest()[:16]


def load_round_schedule(path: Path | None = None) -> dict:
    schedule_path = path or ROUNDS_DIR / "current.json"
    if not schedule_path.exists():
        raise FileNotFoundError(
            f"Arquivo de rodada não encontrado: {schedule_path}. "
            "Edite data/rounds/current.json com os jogos da rodada."
        )
    return json.loads(schedule_path.read_text(encoding="utf-8"))


def schedule_to_matches(schedule: dict) -> list[dict]:
    season = schedule.get("season", datetime.now().year)
    competition = schedule.get("competition", "Brasileirão")
    round_number = schedule["round"]
    matches = []

    for game in schedule["matches"]:
        home = game["home_team"]
        away = game["away_team"]
        match_date = game.get("match_date")
        if match_date:
            match_date = pd.to_datetime(match_date, utc=True).to_pydatetime()
        else:
            match_date = datetime.now(timezone.utc)

        matches.append({
            "match_id": _make_match_id(home, away, round_number),
            "home_team": home,
            "away_team": away,
            "round_number": round_number,
            "competition": competition,
            "match_date": match_date,
            "season": season,
            "label": None,
        })
    return matches


def predict_round(
    schedule_path: Path | None = None,
    save: bool = True,
) -> list[dict]:
    schedule = load_round_schedule(schedule_path)
    matches = schedule_to_matches(schedule)
    silver_df = load_silver()
    fixtures_df = load_fixtures()

    results = []
    contexts = []

    for m in matches:
        context = build_gold_for_match(
            match_id=m["match_id"],
            home_team=m["home_team"],
            away_team=m["away_team"],
            round_number=m["round_number"],
            competition=m["competition"],
            match_date=m["match_date"],
            silver_df=silver_df,
            season=m.get("season"),
            fixtures_df=fixtures_df if not fixtures_df.empty else None,
            live_mode=True,
        )
        prediction, confidence, reason = predict_baseline(context.features)
        entry = {
            "match_id": context.match_id,
            "home_team": context.home_team,
            "away_team": context.away_team,
            "round_number": context.round_number,
            "prediction": prediction,
            "confidence": round(confidence, 2),
            "reason": reason,
            "news_count": context.features.news_count_home + context.features.news_count_away,
            "home_position": context.features.home_position,
            "away_position": context.features.away_position,
        }
        results.append(entry)
        contexts.append(context)

    if save:
        save_gold(contexts, suffix=f"rodada_{schedule['round']}_live")

    return results


def print_predictions(results: list[dict], schedule: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  RODADA {schedule['round']} — {schedule.get('competition', 'Brasileirão')}")
    print(f"{'='*60}\n")
    print(f"{'Mandante':<18} {'Visitante':<18} {'Palpite':>7} {'Conf.':>6}  Motivo")
    print("-" * 70)
    for r in results:
        print(
            f"{r['home_team']:<18} {r['away_team']:<18} "
            f"{r['prediction']:>7} {r['confidence']:>5.0%}  {r['reason']}"
        )
    print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Palpites da rodada atual (notícias + estatísticas)")
    parser.add_argument("--schedule", type=Path, help="JSON da rodada (default: data/rounds/current.json)")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args()

    schedule = load_round_schedule(args.schedule)
    results = predict_round(schedule_path=args.schedule)

    if args.json:
        print(json.dumps({"round": schedule["round"], "predictions": results}, ensure_ascii=False, indent=2))
    else:
        print_predictions(results, schedule)


if __name__ == "__main__":
    main()
