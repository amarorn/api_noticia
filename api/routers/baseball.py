"""Rotas ao vivo para beisebol (MLB / KBO / NPB)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    BaseballSuperbetEventResponse,
    BaseballSuperbetLiveAdviceResponse,
    BaseballSuperbetLiveEventResponse,
    BaseballSuperbetLiveResponse,
)
from config import settings
from ingest.superbet.baseball_advice import SuperbetClientError, run_baseball_live_advice
from ingest.superbet.client import SuperbetClient
from ingest.superbet.store import fetch_event_with_stale_fallback

router = APIRouter(prefix="/baseball")


@router.get("/superbet/live", response_model=BaseballSuperbetLiveResponse)
def baseball_superbet_live(
    sport_id: int = Query(None),
    all_sports: bool = Query(False),
):
    """Lista eventos ao vivo de beisebol na Superbet."""
    filter_sport = None if all_sports else (
        sport_id if sport_id is not None else settings.baseball_sport_id
    )
    try:
        events = SuperbetClient().fetch_live_events(sport_id=filter_sport)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    captured_at = datetime.now(UTC).isoformat()
    payload = [BaseballSuperbetLiveEventResponse(**event.to_dict()) for event in events]
    return BaseballSuperbetLiveResponse(
        count=len(payload),
        sport_id=filter_sport,
        events=payload,
        captured_at=captured_at,
    )


@router.get("/superbet/events/{event_id}", response_model=BaseballSuperbetEventResponse)
async def baseball_superbet_event(event_id: int, save_bronze: bool = Query(True)):
    """Retorna snapshot bruto de um evento de beisebol Superbet."""
    client = SuperbetClient()
    try:
        snapshot, superbet_stale = await asyncio.to_thread(
            fetch_event_with_stale_fallback, client, event_id
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if save_bronze and not superbet_stale:
        from ingest.superbet.store import save_event_snapshot

        try:
            save_event_snapshot(snapshot)
        except Exception:
            pass

    data = snapshot.to_dict()
    return BaseballSuperbetEventResponse(
        event_id=data["event_id"],
        home_team=data["home_team"],
        away_team=data["away_team"],
        event_name=data["event_name"],
        utc_date=data.get("utc_date"),
        betradar_id=data.get("betradar_id"),
        is_live=data["is_live"],
        inplay=data.get("inplay"),
        moneyline_odds=data.get("moneyline_odds") or {},
        moneyline_implied=data.get("moneyline_implied") or {},
        spread_odds=data.get("spread_odds") or {},
        spread_implied=data.get("spread_implied") or {},
        total_points_odds=data.get("total_points_odds") or {},
        total_points_implied=data.get("total_points_implied") or {},
        raw_market_count=data.get("raw_market_count") or 0,
        captured_at=data.get("captured_at") or "",
        superbet_stale=superbet_stale,
    )


@router.get("/superbet/live/{event_id}/advice", response_model=BaseballSuperbetLiveAdviceResponse)
async def baseball_superbet_live_advice(
    event_id: int,
    bankroll: float = Query(1000, gt=0),
    fast: bool = Query(False),
):
    """Retorna advice in-play para um evento de beisebol Superbet."""
    try:
        payload = await asyncio.to_thread(
            run_baseball_live_advice,
            event_id,
            bankroll=bankroll,
            save_bronze=not fast,
            fast=fast,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return BaseballSuperbetLiveAdviceResponse(**payload)
