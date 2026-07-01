"""Roteador live_service: endpoints de apostas in-play ao vivo.

Pode ser montado em qualquer app FastAPI via:
    from live_service.router import live_router
    app.include_router(live_router, prefix="/worldcup/superbet")

Ou usado standalone via live_service/app.py.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from live_service.dependencies import PredictorDep

live_router = APIRouter(tags=["live"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@live_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "live_service"}


# ---------------------------------------------------------------------------
# Lista de eventos ao vivo
# ---------------------------------------------------------------------------

@live_router.get("/live")
def list_live_events(
    sport_id: int = Query(5, description="Filtra por esporte (5=futebol)"),
    all_sports: bool = Query(False, description="Ignora sport_id"),
    rank: bool = Query(True, description="Ordena por score de palpite"),
) -> dict[str, Any]:
    """Lista jogos ao vivo na Superbet com ranking de palpites."""
    from datetime import datetime, timezone

    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.live_rank import rank_live_events

    filter_sport = None if all_sports else sport_id
    try:
        events = SuperbetClient().fetch_live_events(sport_id=filter_sport)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if rank:
        ranked = rank_live_events(events)
        payload = [
            {**event.to_dict(), **bet_rank.to_dict()}
            for event, bet_rank in ranked
        ]
    else:
        payload = [event.to_dict() for event in events]

    return {
        "count": len(payload),
        "sport_id": filter_sport,
        "events": payload,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Melhores picks ao vivo
# ---------------------------------------------------------------------------

@live_router.get("/live/best-picks")
async def best_picks(
    predictor: PredictorDep,
    min_ev: float = Query(0.05, description="EV mínimo (ex: 0.05 = 5%)"),
    min_confidence: float = Query(0.0, description="Confiança mínima (0–1)"),
    bankroll: float = Query(1000, gt=0),
    sport_id: int = Query(5),
    fast: bool = Query(True),
) -> dict[str, Any]:
    """Varre todos os eventos ao vivo e retorna os melhores picks."""
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.advice import run_live_advice

    try:
        events = SuperbetClient().fetch_live_events(sport_id=sport_id)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    picks: list[dict[str, Any]] = []
    for ev in events:
        try:
            advice = await asyncio.to_thread(
                run_live_advice,
                ev.event_id,
                predictor,
                bankroll=bankroll,
                save_bronze=False,
                save_tick=False,
                use_sofascore_live=False,
                fast=True,
            )
        except Exception:
            continue

        for opp in (advice.get("opportunities") or []):
            ev_val = opp.get("ev") or 0
            conf = opp.get("confidence") or 0
            if ev_val >= min_ev and conf >= min_confidence:
                picks.append({
                    "event_id": ev.event_id,
                    "home_team": advice.get("home_team"),
                    "away_team": advice.get("away_team"),
                    "minute": advice.get("minute", 0),
                    **opp,
                })

    picks.sort(key=lambda x: x.get("ev", 0), reverse=True)
    return {"count": len(picks), "picks": picks}


# ---------------------------------------------------------------------------
# Advice por evento
# ---------------------------------------------------------------------------

@live_router.get("/live/{event_id}/advice")
async def live_advice(
    event_id: int,
    predictor: PredictorDep,
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
    market: str | None = Query(None),
    outcome: str | None = Query(None),
    stake: float | None = Query(None, gt=0),
    odds_placed: float | None = Query(None, gt=1),
    fast: bool = Query(False),
    kickoff: str | None = Query(None),
) -> dict[str, Any]:
    """Captura Superbet ao vivo e retorna advice completo."""
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_bet_advice import UserBetInput

    user_bet = None
    if market and outcome and stake is not None and odds_placed is not None:
        user_bet = UserBetInput(
            market=market,
            outcome=outcome,
            stake=stake,
            odds_placed=odds_placed,
        )

    try:
        payload = await asyncio.to_thread(
            run_live_advice,
            event_id,
            predictor,
            phase=phase,
            bankroll=bankroll,
            user_bet=user_bet,
            save_bronze=not fast,
            save_tick=not fast,
            use_sofascore_live=False if fast else None,
            fast=fast,
            kickoff=kickoff,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return payload


# ---------------------------------------------------------------------------
# Bilhetes otimizados
# ---------------------------------------------------------------------------

@live_router.get("/live/{event_id}/optimized-tickets")
async def optimized_tickets(
    event_id: int,
    predictor: PredictorDep,
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
    max_legs: int = Query(4, ge=2, le=6),
    min_legs: int = Query(2, ge=2, le=4),
    top_k: int = Query(5, ge=1, le=10),
    fast: bool = Query(False),
) -> dict[str, Any]:
    """Retorna bilhetes otimizados por EV para o evento."""
    from datetime import UTC, datetime

    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_combo_optimizer import build_optimized_tickets, tickets_to_dict

    try:
        payload = await asyncio.to_thread(
            run_live_advice,
            event_id,
            predictor,
            phase=phase,
            bankroll=bankroll,
            save_bronze=not fast,
            save_tick=not fast,
            use_sofascore_live=False if fast else None,
            fast=fast,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    strategy = payload.get("strategy") or {}
    market_scan = strategy.get("market_scan") or []
    current_score = payload.get("current_score") or "0x0"
    try:
        home_score, away_score = map(int, current_score.split("x"))
    except ValueError:
        home_score, away_score = 0, 0

    minute = payload.get("minute", 0)
    tickets_by_period = build_optimized_tickets(
        market_scan,
        minute=minute,
        home_score=home_score,
        away_score=away_score,
        bankroll=bankroll,
        max_legs=max_legs,
        min_legs=min_legs,
        top_k=top_k,
    )
    td = tickets_to_dict(tickets_by_period)

    return {
        "event_id": str(event_id),
        "home_team": payload.get("home_team"),
        "away_team": payload.get("away_team"),
        "minute": minute,
        "home_score": home_score,
        "away_score": away_score,
        "tickets_1h": td.get("1h", []),
        "tickets_2h": td.get("2h", []),
        "tickets_ft": td.get("ft", []),
        "tickets_mixed": td.get("mixed", []),
        "total_tickets": sum(len(td.get(k, [])) for k in ("1h", "2h", "ft", "mixed")),
        "generated_at": datetime.now(UTC).isoformat(),
    }
