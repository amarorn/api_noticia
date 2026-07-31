"""Sincroniza ``data/rounds/current.json`` a partir de fixtures importadas."""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from ingest.fixtures.store import load_fixtures

ROUNDS_DIR = Path("data/rounds")
COMPETITION_KEYS = {
    "brasileirao": ("Brasileirão", "brasileirao"),
    "serie_b": ("Brasileirão Série B", "brasileirao_serie_b"),
}


def latest_round_by_schedule(
    season: int,
    *,
    competition_key: str = "brasileirao",
) -> int:
    """Rodada cuja última partida é a mais recente no passado (≤ hoje+1d)."""
    _, store_key = COMPETITION_KEYS.get(competition_key, ("Brasileirão", "brasileirao"))
    df = load_fixtures(season=season, competition=store_key)
    if df.empty:
        df = load_fixtures(competition=store_key)
    if df.empty:
        return 1

    df = df.copy()
    df["match_date"] = pd.to_datetime(df["match_date"], utc=True)
    now = pd.Timestamp.now(tz="UTC")
    by_round = df.groupby("round_number")["match_date"].max()
    eligible = by_round[by_round <= now + pd.Timedelta(days=1)]
    if not eligible.empty:
        return int(eligible.idxmax())
    return int(by_round.idxmin())


def build_round_schedule(
    season: int,
    round_number: int,
    *,
    competition_key: str = "brasileirao",
) -> dict:
    label, store_key = COMPETITION_KEYS.get(competition_key, ("Brasileirão", "brasileirao"))
    df = load_fixtures(season=season, competition=store_key)
    if df.empty:
        df = load_fixtures(competition=store_key)
    if df.empty:
        raise FileNotFoundError(
            f"Sem fixtures para {label}. Execute: import-fixtures --competition {competition_key}"
        )

    rnd = df[df["round_number"] == round_number].sort_values("match_date")
    if rnd.empty:
        raise ValueError(f"Rodada {round_number} não encontrada na temporada {season}")

    matches = []
    for _, row in rnd.iterrows():
        md = row["match_date"]
        if pd.notna(md):
            md = pd.to_datetime(md, utc=True).to_pydatetime().isoformat()
        matches.append(
            {
                "home_team": str(row["home_team"]),
                "away_team": str(row["away_team"]),
                "match_date": md,
            }
        )

    return {
        "season": season,
        "competition": label,
        "round": int(round_number),
        "matches": matches,
    }


def sync_current_round(
    *,
    season: int | None = None,
    round_number: int | None = None,
    competition_key: str = "brasileirao",
    output_path: Path | None = None,
) -> Path:
    season = season or datetime.now(UTC).year
    rnd = round_number or latest_round_by_schedule(season, competition_key=competition_key)
    schedule = build_round_schedule(season, rnd, competition_key=competition_key)
    out = output_path or ROUNDS_DIR / "current.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera data/rounds/current.json a partir de fixtures openfootball"
    )
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--round", type=int, default=None, help="Rodada (default: auto por calendário)")
    parser.add_argument(
        "--competition",
        choices=list(COMPETITION_KEYS.keys()),
        default="brasileirao",
    )
    parser.add_argument("--output", type=Path, default=ROUNDS_DIR / "current.json")
    args = parser.parse_args()

    path = sync_current_round(
        season=args.season,
        round_number=args.round,
        competition_key=args.competition,
        output_path=args.output,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    print(
        f"Gravado {path}: {data['competition']} rodada {data['round']} "
        f"({len(data['matches'])} jogos, season={data['season']})"
    )


if __name__ == "__main__":
    main()
