#!/usr/bin/env python3
"""Busca snapshot Superbet e atualiza odds de mercado para treino/inferência."""
from __future__ import annotations

import argparse
from pathlib import Path

from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.store import merge_snapshot_into_odds_file, save_event_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot Superbet → lake + superbet_odds.json")
    parser.add_argument("--event-id", type=int, required=True, help="ID do evento Superbet")
    parser.add_argument(
        "--merge-odds",
        action="store_true",
        help="Atualiza data/rounds/superbet_odds.json para features de mercado",
    )
    parser.add_argument(
        "--output-odds",
        type=Path,
        default=Path("data/rounds/superbet_odds.json"),
    )
    args = parser.parse_args()

    try:
        snapshot = SuperbetClient().fetch_event(args.event_id)
    except SuperbetClientError as exc:
        print(f"Erro: {exc}")
        return 1

    bronze_path = save_event_snapshot(snapshot)
    print(f"Bronze: {bronze_path}")
    print(f"Jogo: {snapshot.home_team} x {snapshot.away_team}")
    if snapshot.inplay:
        ip = snapshot.inplay
        print(f"Ao vivo: {ip.home_score}x{ip.away_score} @ {ip.minute}'")
    if snapshot.h2h_odds:
        print(f"1X2: {snapshot.h2h_odds} → implícitas {snapshot.h2h_implied}")

    if args.merge_odds:
        out = merge_snapshot_into_odds_file(snapshot, args.output_odds)
        print(f"Odds merge: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
