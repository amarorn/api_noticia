"""Captura contínua de ticks Superbet ao vivo → bronze + live_ticks.parquet.

Cada poll chama run_live_advice (modelo + EV + cash-out) e grava:
- data/lake/bronze/superbet/events/{id}/*.json  (snapshots)
- data/lake/bronze/superbet/live_ticks.parquet   (benchmark)

CLI: poll-superbet-live --auto --interval 120
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from config import settings

from ingest.superbet.advice import run_live_advice
from ingest.superbet.baseball_advice import run_baseball_live_advice
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.team_resolver import is_international_match
from ingest.superbet.event_finalize import (
    list_pending_watch_event_ids,
    mark_event_watchlist_discarded,
    sweep_stale_watchlist_events,
    try_finalize_from_bronze,
)
from ingest.superbet.live_ticks import live_ticks_path
from ingest.superbet.parser import SuperbetLiveEventSummary
from ingest.superbet.store import is_valid_superbet_event_id
from models.wc_artifact import load_or_train_wc_predictor

logger = logging.getLogger(__name__)


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


def _filter_superbet_event_ids(event_ids: list[int]) -> list[int]:
    """Remove IDs de teste ou bronze local inválido (ex.: event_id=123)."""
    return [eid for eid in event_ids if is_valid_superbet_event_id(eid)]


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
        return _filter_superbet_event_ids(
            event_ids[:max_events] if max_events else event_ids
        )
    if not auto:
        return []
    events = client.fetch_live_events(sport_id=sport_id)
    events = _filter_live_events(events, filter_international=filter_international)
    ids = [e.event_id for e in events if e.event_id > 0]
    return _filter_superbet_event_ids(ids[:max_events] if max_events else ids)


def _resolve_event_ids_resilient(
    client: SuperbetClient,
    *,
    event_ids: list[int] | None,
    auto: bool,
    sport_id: int,
    max_events: int | None = None,
    filter_international: bool = False,
    last_auto_ids: list[int] | None = None,
) -> tuple[list[int], list[int] | None]:
    """Resolve IDs do ciclo; em falha de rede reutiliza último snapshot auto."""
    try:
        ids = _resolve_event_ids(
            client,
            event_ids=event_ids,
            auto=auto,
            sport_id=sport_id,
            max_events=max_events,
            filter_international=filter_international,
        )
    except SuperbetClientError as exc:
        cached = list(last_auto_ids or [])
        logger.warning(
            "superbet_resolve_event_ids_failed: %s (cached=%d)",
            exc,
            len(cached),
        )
        print(f"Superbet indisponível: {exc}")
        if cached:
            print(f"Reutilizando {len(cached)} evento(s) do último ciclo OK.")
            return cached, last_auto_ids
        print("Nenhum evento em cache; aguardando próximo ciclo.")
        return [], last_auto_ids

    if auto and not event_ids and ids:
        return ids, list(ids)
    return ids, last_auto_ids


def _merge_poll_event_ids(
    *,
    resolved: list[int],
    watchlist: set[int],
) -> list[int]:
    """Une feed ao vivo + watchlist (jogos vistos que ainda não finalizaram)."""
    if not settings.superbet_poll_watchlist_enabled:
        return list(dict.fromkeys(resolved))
    cap = settings.superbet_poll_watchlist_max
    merged: list[int] = []
    for eid in [*resolved, *sorted(watchlist)]:
        if not is_valid_superbet_event_id(eid):
            continue
        if eid not in merged:
            merged.append(eid)
        if len(merged) >= cap:
            break
    return merged


def poll_once(
    event_ids: list[int],
    predictor,
    *,
    phase: str = "friendly",
    bankroll: float = 1000.0,
    client: SuperbetClient | None = None,
    watchlist: set[int] | None = None,
    fast: bool = False,
) -> dict:
    """Executa um ciclo de poll para os event_ids informados.

    fast=True pula a pesquisa ao vivo (Gemini) por evento — cada chamada leva
    ~2min, o que faz um ciclo com vários jogos monitorados nunca respeitar o
    --interval e saturar a CPU/rede compartilhada com o resto da API.
    """
    superbet_client = client or SuperbetClient()
    captured = 0
    skipped = 0
    errors = 0
    details: list[str] = []
    active_watch: set[int] = set(watchlist or [])

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
                fast=fast,
            )
        except SuperbetClientError as exc:
            errors += 1
            if not is_valid_superbet_event_id(event_id):
                active_watch.discard(event_id)
            elif try_finalize_from_bronze(event_id):
                active_watch.discard(event_id)
                captured += 1
                msg = f"[{event_id}] encerrado via bronze (API indisponível)"
                details.append(msg)
                print(msg)
                continue
            elif "400" in str(exc) or "404" in str(exc):
                mark_event_watchlist_discarded(event_id, f"api_{exc}")
                active_watch.discard(event_id)
            msg = f"[{event_id}] erro API: {exc}"
            details.append(msg)
            logger.warning(msg)
            continue

        if not payload.get("is_live"):
            if payload.get("is_finished"):
                active_watch.discard(event_id)
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
                if event_id in active_watch:
                    captured += 1
                    msg = (
                        f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
                        f"— watchlist ({payload.get('status') or 'sem stats'}) "
                        f"{payload.get('current_score')} @ {payload.get('minute')}'"
                    )
                    details.append(msg)
                    print(msg)
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

        active_watch.add(event_id)
        captured += 1
        aportes = len(payload.get("aportes") or [])
        msg = (
            f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
            f"{payload.get('current_score')} @ {payload.get('minute')}' "
            f"— {aportes} aportes"
        )
        try:
            from models.live_llm_copilot import warm_live_copilot

            copilot = warm_live_copilot(payload, sport="football")
            if copilot and copilot.get("acao_agora") == "apostar":
                picks = copilot.get("picks") or []
                pick_label = picks[0].get("label") if picks else ""
                if pick_label:
                    msg += f" · copilot: {pick_label}"
        except Exception:
            pass
        details.append(msg)
        print(msg)

    return {
        "captured": captured,
        "skipped": skipped,
        "errors": errors,
        "n_events": len(event_ids),
        "details": details,
        "watchlist": active_watch,
    }


def poll_once_baseball(
    event_ids: list[int],
    *,
    bankroll: float = 1000.0,
    client: SuperbetClient | None = None,
    watchlist: set[int] | None = None,
    fast: bool = False,
) -> dict:
    """Ciclo de poll beisebol (sem WcPredictor)."""
    superbet_client = client or SuperbetClient()
    captured = 0
    skipped = 0
    errors = 0
    details: list[str] = []
    active_watch: set[int] = set(watchlist or [])

    for event_id in event_ids:
        try:
            payload = run_baseball_live_advice(
                event_id,
                bankroll=bankroll,
                save_bronze=True,
                save_tick=True,
                fast=fast,
                client=superbet_client,
            )
        except SuperbetClientError as exc:
            errors += 1
            if not is_valid_superbet_event_id(event_id):
                active_watch.discard(event_id)
            elif try_finalize_from_bronze(event_id):
                active_watch.discard(event_id)
                captured += 1
                msg = f"[{event_id}] encerrado via bronze (API indisponível)"
                details.append(msg)
                print(msg)
                continue
            elif "400" in str(exc) or "404" in str(exc):
                mark_event_watchlist_discarded(event_id, f"api_{exc}")
                active_watch.discard(event_id)
            msg = f"[{event_id}] erro API: {exc}"
            details.append(msg)
            logger.warning(msg)
            continue

        inning = payload.get("inning") or payload.get("minute") or 0
        if not payload.get("is_live"):
            if payload.get("is_finished"):
                active_watch.discard(event_id)
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
                if event_id in active_watch:
                    captured += 1
                    msg = (
                        f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
                        f"— watchlist ({payload.get('status') or 'sem stats'}) "
                        f"{payload.get('current_score')} @ {inning}I"
                    )
                    details.append(msg)
                    print(msg)
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

        active_watch.add(event_id)
        captured += 1
        aportes = len(payload.get("aportes") or [])
        posture = (payload.get("strategy") or {}).get("posture")
        msg = (
            f"[{event_id}] {payload.get('home_team')} x {payload.get('away_team')} "
            f"{payload.get('current_score')} @ {inning}I "
            f"— {aportes} aportes"
        )
        if posture:
            msg += f" · {posture}"
        try:
            from models.live_llm_copilot import warm_live_copilot

            copilot = warm_live_copilot(payload, sport="baseball")
            if copilot and copilot.get("acao_agora") == "apostar":
                picks = copilot.get("picks") or []
                pick_label = picks[0].get("label") if picks else ""
                if pick_label:
                    msg += f" · copilot: {pick_label}"
        except Exception:
            pass
        details.append(msg)
        print(msg)

    return {
        "captured": captured,
        "skipped": skipped,
        "errors": errors,
        "n_events": len(event_ids),
        "details": details,
        "watchlist": active_watch,
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
    fast: bool = False,
    sport: str = "football",
) -> int:
    """Loop de captura até max_cycles ou Ctrl+C."""
    client = SuperbetClient()
    cycle = 0
    last_auto_ids: list[int] | None = None

    watchlist: set[int] = set(
        list_pending_watch_event_ids(max_events=settings.superbet_poll_watchlist_max)
    )
    if watchlist:
        print(f"Watchlist retomada: {len(watchlist)} evento(s) pendente(s)")

    print(f"Ticks parquet: {live_ticks_path()}")
    print(f"Intervalo: {interval_sec}s | auto={auto} | sport_id={sport_id} | sport={sport}")

    predictor = None
    if sport == "football":
        predictor, _manifest = load_or_train_wc_predictor(allow_train=allow_train)

    while True:
        cycle += 1
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ids, last_auto_ids = _resolve_event_ids_resilient(
            client,
            event_ids=event_ids,
            auto=auto,
            sport_id=sport_id,
            max_events=max_events,
            filter_international=filter_international,
            last_auto_ids=last_auto_ids,
        )

        print(f"\n--- Ciclo {cycle} @ {ts} | {len(ids)} ao vivo + {len(watchlist)} watch ---")

        if watchlist and settings.superbet_watchlist_sweep_enabled:
            swept = sweep_stale_watchlist_events(
                sorted(watchlist),
                live_event_ids=set(ids),
            )
            for row in swept:
                watchlist.discard(int(row["event_id"]))
            if swept:
                n_fin = sum(1 for r in swept if r.get("action") == "finalized")
                n_disc = sum(1 for r in swept if r.get("action") == "discarded")
                print(
                    f"Watchlist sweep: {n_fin} finalizado(s), {n_disc} descartado(s)"
                )

        merged_ids = _merge_poll_event_ids(resolved=ids, watchlist=watchlist)
        if not merged_ids:
            print("Nenhum evento ao vivo encontrado.")
        else:
            if sport == "baseball":
                result = poll_once_baseball(
                    merged_ids,
                    bankroll=bankroll,
                    client=client,
                    watchlist=watchlist,
                    fast=fast,
                )
            else:
                result = poll_once(
                    merged_ids,
                    predictor,
                    phase=phase,
                    bankroll=bankroll,
                    client=client,
                    watchlist=watchlist,
                    fast=fast,
                )
            watchlist = set(result.get("watchlist") or watchlist)
            print(
                f"Resumo: {result['captured']} capturados, "
                f"{result['skipped']} ignorados, {result['errors']} erros, "
                f"watchlist={len(watchlist)}"
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
    parser.add_argument(
        "--baseball",
        action="store_true",
        help=f"Atalho beisebol: --auto --sport-id {settings.baseball_sport_id} (sem WC predictor)",
    )
    parser.add_argument("--sport-id", type=int, default=5, help="Esporte para --auto (5=futebol, 20=beisebol)")
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
        "--wc-copa",
        action="store_true",
        help="Atalho: --auto --filter-international --phase group (Copa/amistosos seleções)",
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
    parser.add_argument("--phase", default=None, help="Fase do modelo in-play (default: config inplay_default_phase)")
    parser.add_argument("--bankroll", type=float, default=1000.0, help="Bankroll para Kelly/EV")
    parser.add_argument(
        "--no-train",
        action="store_true",
        help="Falha se predictor.pkl estiver ausente/desatualizado",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Pula pesquisa ao vivo (Gemini) por evento — cada chamada leva ~2min e "
        "impede o loop de respeitar --interval em ciclos com vários jogos monitorados",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs detalhados")
    args = parser.parse_args()

    if args.phase is None:
        args.phase = settings.inplay_default_phase

    if args.wc_copa:
        args.auto = True
        args.filter_international = True
        if args.phase == "friendly":
            args.phase = settings.superbet_poll_wc_phase
        if args.interval == 0 and settings.superbet_poll_interval_sec > 0:
            args.interval = settings.superbet_poll_interval_sec

    sport = "football"
    if args.baseball:
        args.auto = True
        args.sport_id = settings.baseball_sport_id
        sport = "baseball"
        if args.interval == 0 and settings.superbet_poll_interval_sec > 0:
            args.interval = settings.superbet_poll_interval_sec

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
            fast=args.fast,
            sport=sport,
        )

    # Execução única
    client = SuperbetClient()
    try:
        ids = _resolve_event_ids(
            client,
            event_ids=event_ids,
            auto=args.auto,
            sport_id=args.sport_id,
            max_events=args.max_events,
            filter_international=args.filter_international,
        )
    except SuperbetClientError as exc:
        print(f"Superbet indisponível: {exc}")
        return 1
    if not ids:
        print("Nenhum evento ao vivo encontrado.")
        return 0

    if sport == "baseball":
        result = poll_once_baseball(
            ids, bankroll=args.bankroll, client=client, fast=args.fast
        )
    else:
        predictor, _ = load_or_train_wc_predictor(allow_train=not args.no_train)
        result = poll_once(
            ids, predictor, phase=args.phase, bankroll=args.bankroll, client=client, fast=args.fast
        )
    print(
        f"\nResumo: {result['captured']} capturados, "
        f"{result['skipped']} ignorados, {result['errors']} erros"
    )
    print(f"Ticks: {live_ticks_path()}")
    return 1 if result["errors"] and result["captured"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
