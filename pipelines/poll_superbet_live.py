"""Captura contínua de ticks Superbet ao vivo → bronze + live_ticks.parquet.

Cada poll chama run_live_advice (modelo + EV + cash-out) e grava:
- data/lake/bronze/superbet/events/{id}/*.json  (snapshots)
- data/lake/bronze/superbet/live_ticks.parquet   (benchmark)

CLI: poll-superbet-live --auto --interval 120
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

from functools import lru_cache

from ingest.fifa.teams import FIFA_COUNTRY_CODES
from ingest.superbet.advice import run_live_advice
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.live_ticks import live_ticks_path
from ingest.superbet.parser import SuperbetLiveEventSummary
from models.wc_artifact import load_or_train_wc_predictor
from schemas.national_teams import NATIONAL_ALIASES, normalize_national_team

logger = logging.getLogger(__name__)

_CLUB_MARKERS = (
    " fc",
    " fa",
    " juniors",
    " kopavog",
    "(f)",
    " united fc",
    " city",
    " town",
    " athletic",
    " wanderers",
    " rovers",
    " deportivo",
    " club ",
)


@lru_cache
def _known_national_teams() -> frozenset[str]:
    """Seleções reconhecidas (FIFA + aliases + Copa 2026)."""
    import json
    from pathlib import Path

    teams = set(FIFA_COUNTRY_CODES.keys()) | set(NATIONAL_ALIASES.values())
    wc_path = Path(__file__).resolve().parents[1] / "data" / "rounds" / "wc_2026.json"
    if wc_path.exists():
        data = json.loads(wc_path.read_text(encoding="utf-8"))
        for group in data.get("groups", []):
            teams.update(group.get("teams", []))
    return frozenset(teams)


def _looks_like_club(name: str) -> bool:
    low = name.lower()
    if any(marker in low for marker in _CLUB_MARKERS):
        return True
    if " united" in low and "estados unidos" not in low:
        return True
    return False


def is_international_match(home_team: str, away_team: str) -> bool:
    """Heurística: amistoso/seleção vs seleção (exclui clubes óbvios)."""
    if _looks_like_club(home_team) or _looks_like_club(away_team):
        return False
    known = _known_national_teams()
    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    return home in known and away in known


def _filter_live_events(
    events: list[SuperbetLiveEventSummary],
    *,
    filter_international: bool,
) -> list[SuperbetLiveEventSummary]:
    if not filter_international:
        return events
    kept = [e for e in events if is_international_match(e.home_team, e.away_team)]
    if kept:
        return kept
    logger.warning(
        "filter-international: nenhum amistoso/seleção no feed; %d evento(s) ignorado(s)",
        len(events),
    )
    return []


def _resolve_event_ids(
    client: SuperbetClient,
    *,
    event_ids: list[int] | None,
    auto: bool,
    sport_id: int,
    max_events: int | None = None,
    filter_international: bool = False,
) -> list[int]:
    if event_ids:
        return event_ids[:max_events] if max_events else event_ids
    if not auto:
        return []
    events = client.fetch_live_events(sport_id=sport_id)
    events = _filter_live_events(events, filter_international=filter_international)
    ids = [e.event_id for e in events if e.event_id > 0]
    return ids[:max_events] if max_events else ids


def poll_once(
    event_ids: list[int],
    predictor,
    *,
    phase: str = "friendly",
    bankroll: float = 1000.0,
    client: SuperbetClient | None = None,
) -> dict:
    """Executa um ciclo de poll para os event_ids informados."""
    superbet_client = client or SuperbetClient()
    captured = 0
    skipped = 0
    errors = 0
    details: list[str] = []

    for event_id in event_ids:
        try:
            payload = run_live_advice(
                event_id,
                predictor,
                phase=phase,
                bankroll=bankroll,
                save_bronze=True,
                save_tick=True,
                client=superbet_client,
            )
        except SuperbetClientError as exc:
            errors += 1
            msg = f"[{event_id}] erro API: {exc}"
            details.append(msg)
            logger.warning(msg)
            continue

        if not payload.get("is_live"):
            if payload.get("is_finished"):
                fin = payload.get("event_finalize") or {}
                msg = (
                    f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
                    f"— encerrado {payload.get('current_score')} "
                    f"(gold={'ok' if fin else 'já processado'})"
                )
                if fin.get("retrain_scheduled"):
                    msg += " · retreino agendado"
                details.append(msg)
                print(msg)
                captured += 1
            else:
                skipped += 1
                status = payload.get("status") or "sem stats"
                msg = (
                    f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
                    f"— não ao vivo ({status})"
                )
                details.append(msg)
                print(msg)
            continue

        captured += 1
        aportes = len(payload.get("aportes") or [])
        msg = (
            f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
            f"{payload.get('current_score')} @ {payload.get('minute')}' "
            f"— {aportes} aportes"
        )
        details.append(msg)
        print(msg)

    return {
        "captured": captured,
        "skipped": skipped,
        "errors": errors,
        "n_events": len(event_ids),
        "details": details,
    }


def poll_loop(
    event_ids: list[int] | None,
    *,
    auto: bool = False,
    sport_id: int = 5,
    interval_sec: int = 120,
    phase: str = "friendly",
    bankroll: float = 1000.0,
    allow_train: bool = True,
    max_cycles: int | None = None,
    max_events: int | None = None,
    filter_international: bool = False,
) -> int:
    """Loop de captura até max_cycles ou Ctrl+C."""
    predictor, _manifest = load_or_train_wc_predictor(allow_train=allow_train)
    client = SuperbetClient()
    cycle = 0

    print(f"Ticks parquet: {live_ticks_path()}")
    print(f"Intervalo: {interval_sec}s | auto={auto} | sport_id={sport_id}")

    while True:
        cycle += 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ids = _resolve_event_ids(
            client,
            event_ids=event_ids,
            auto=auto,
            sport_id=sport_id,
            max_events=max_events,
            filter_international=filter_international,
        )

        print(f"\n--- Ciclo {cycle} @ {ts} | {len(ids)} evento(s) ---")
        if not ids:
            print("Nenhum evento ao vivo encontrado.")
        else:
            result = poll_once(ids, predictor, phase=phase, bankroll=bankroll, client=client)
            print(
                f"Resumo: {result['captured']} capturados, "
                f"{result['skipped']} ignorados, {result['errors']} erros"
            )

        if max_cycles is not None and cycle >= max_cycles:
            break

        try:
            time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\nPoll interrompido pelo usuário.")
            return 0

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Poll Superbet ao vivo → bronze + live_ticks.parquet"
    )
    parser.add_argument(
        "--event-ids",
        help="IDs separados por vírgula (ex: 13108472,13324536). Opcional com --auto.",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Descobre jogos ao vivo automaticamente (sport_id=5 futebol).",
    )
    parser.add_argument("--sport-id", type=int, default=5, help="Esporte para --auto (5=futebol)")
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Limite de eventos por ciclo (útil com --auto para não varrer dezenas de jogos)",
    )
    parser.add_argument(
        "--filter-international",
        action="store_true",
        help="Com --auto: só seleções/amistosos (ignora clubes no feed ao vivo)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Segundos entre ciclos (0=uma única execução, ex: 120 para loop contínuo)",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Limite de ciclos no loop (padrão: infinito até Ctrl+C)",
    )
    parser.add_argument("--phase", default="friendly", help="Fase do modelo WC")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Bankroll para Kelly/EV")
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Falha se predictor.pkl estiver ausente/desatualizado",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs detalhados")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    event_ids: list[int] | None = None
    if args.event_ids:
        event_ids = [int(x.strip()) for x in args.event_ids.split(",") if x.strip()]

    if not event_ids and not args.auto:
        parser.error("Informe --event-ids ou use --auto para descobrir jogos ao vivo.")

    if args.interval > 0 or args.max_cycles:
        return poll_loop(
            event_ids,
            auto=args.auto,
            sport_id=args.sport_id,
            interval_sec=args.interval or 120,
            phase=args.phase,
            bankroll=args.bankroll,
            allow_train=not args.no_train,
            max_cycles=args.max_cycles,
            max_events=args.max_events,
            filter_international=args.filter_international,
        )

    # Execução única
    predictor, _ = load_or_train_wc_predictor(allow_train=not args.no_train)
    client = SuperbetClient()
    ids = _resolve_event_ids(
        client,
        event_ids=event_ids,
        auto=args.auto,
        sport_id=args.sport_id,
        max_events=args.max_events,
        filter_international=args.filter_international,
    )
    if not ids:
        print("Nenhum evento ao vivo encontrado.")
        return 0
    result = poll_once(ids, predictor, phase=args.phase, bankroll=args.bankroll, client=client)
    print(
        f"\nResumo: {result['captured']} capturados, "
        f"{result['skipped']} ignorados, {result['errors']} erros"
    )
    print(f"Ticks: {live_ticks_path()}")
    return 1 if result["errors"] and result["captured"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
