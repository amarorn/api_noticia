#!/usr/bin/env python3
"""Captura snapshots Superbet de jogos ao vivo e grava recomendações no lake."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.store import save_event_snapshot
from models.wc_bet_advice import UserBetInput, build_bet_advice_report
from models.wc_inplay import inplay_from_predictor
from models.wc_artifact import load_or_train_wc_predictor


def poll_events(event_ids: list[int], bets_file: Path | None, *, allow_train: bool) -> int:
    predictor, _manifest = load_or_train_wc_predictor(allow_train=allow_train)
    client = SuperbetClient()
    bets_by_event: dict[int, list[dict]] = {}
    if bets_file and bets_file.exists():
        payload = json.loads(bets_file.read_text(encoding="utf-8"))
        for row in payload.get("bets", []):
            eid = int(row["superbet_event_id"])
            bets_by_event.setdefault(eid, []).append(row)

    out_dir = Path("data/lake/bronze/superbet/live_poll")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: list[dict] = []

    for event_id in event_ids:
        try:
            snapshot = client.fetch_event(event_id)
        except SuperbetClientError as exc:
            print(f"[{event_id}] erro: {exc}")
            continue

        save_event_snapshot(snapshot)
        if not snapshot.inplay or snapshot.inplay.status not in {"STARTED", "LIVE"}:
            print(f"[{event_id}] {snapshot.home_team} x {snapshot.away_team} — não ao vivo ({snapshot.inplay.status if snapshot.inplay else 'sem stats'})")
            continue

        ip = snapshot.inplay
        result = inplay_from_predictor(
            predictor,
            home_team=snapshot.home_team,
            away_team=snapshot.away_team,
            home_score=ip.home_score,
            away_score=ip.away_score,
            minute=ip.minute,
            phase="friendly",
            ht_home_score=ip.ht_home_score,
            ht_away_score=ip.ht_away_score,
        )
        inplay_dict = result.to_dict()
        user_bets = bets_by_event.get(event_id, [])
        bet_reports = []
        for b in user_bets:
            bet = UserBetInput(
                market=b["market"],
                outcome=b["outcome"],
                stake=float(b["stake"]),
                odds_placed=float(b["odds_placed"]),
            )
            report = build_bet_advice_report(
                home_team=snapshot.home_team,
                away_team=snapshot.away_team,
                inplay=inplay_dict,
                snapshot=snapshot,
                user_bet=bet,
                minute=ip.minute,
                bankroll=float(b.get("bankroll", 1000)),
            )
            bet_reports.append(report)

        aporte_only = build_bet_advice_report(
            home_team=snapshot.home_team,
            away_team=snapshot.away_team,
            inplay=inplay_dict,
            snapshot=snapshot,
            user_bet=None,
            minute=ip.minute,
        )

        row = {
            "event_id": event_id,
            "match": f"{snapshot.home_team} x {snapshot.away_team}",
            "score": inplay_dict["current_score"],
            "minute": ip.minute,
            "captured_at": ts,
            "user_bets": bet_reports,
            "aportes": aporte_only["aportes"],
        }
        results.append(row)
        print(f"[{event_id}] {row['match']} {row['score']} @ {row['minute']}' — {len(aporte_only['aportes'])} aportes")

    if results:
        path = out_dir / f"{ts}.json"
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Salvo: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll Superbet ao vivo → modelo → cash-out/aporte")
    parser.add_argument("--event-ids", required=True, help="IDs separados por vírgula, ex: 13247229,123")
    parser.add_argument("--bets-file", type=Path, default=Path("data/superbet_active_bets.json"))
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Falha se predictor.pkl estiver ausente/desatualizado (não retreina)",
    )
    args = parser.parse_args()
    ids = [int(x.strip()) for x in args.event_ids.split(",") if x.strip()]
    return poll_events(ids, args.bets_file, allow_train=not args.no_train)


if __name__ == "__main__":
    raise SystemExit(main())
