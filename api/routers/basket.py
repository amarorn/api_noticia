"""Rotas ao vivo para basquete (NBA)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    BasketSuperbetEventResponse,
    BasketSuperbetLiveAdviceResponse,
    BasketSuperbetLiveEventResponse,
    BasketSuperbetLiveResponse,
    LiveCopilotAgentRequest,
    LiveCopilotAgentResponse,
    LiveCopilotResponse,
)
from config import settings
from ingest.superbet.basket_advice import SuperbetClientError, run_basket_live_advice
from ingest.superbet.client import SuperbetClient
from ingest.superbet.store import fetch_event_with_stale_fallback

router = APIRouter(prefix="/basket")


@router.get("/superbet/live", response_model=BasketSuperbetLiveResponse)
def basket_superbet_live(
    sport_id: int = Query(None),
    all_sports: bool = Query(False),
):
    """Lista eventos ao vivo de basquete na Superbet."""
    filter_sport = None if all_sports else (sport_id if sport_id is not None else settings.basket_sport_id)
    try:
        events = SuperbetClient().fetch_live_events(sport_id=filter_sport)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    captured_at = datetime.now(UTC).isoformat()
    payload = [BasketSuperbetLiveEventResponse(**event.to_dict()) for event in events]
    return BasketSuperbetLiveResponse(
        count=len(payload),
        sport_id=filter_sport,
        events=payload,
        captured_at=captured_at,
    )


@router.get("/superbet/events/{event_id}", response_model=BasketSuperbetEventResponse)
async def basket_superbet_event(event_id: int, save_bronze: bool = Query(True)):
    """Retorna snapshot bruto de um evento de basquete Superbet."""
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

    return BasketSuperbetEventResponse(**snapshot.to_dict(), superbet_stale=superbet_stale)


@router.get("/superbet/live/{event_id}/advice", response_model=BasketSuperbetLiveAdviceResponse)
async def basket_superbet_live_advice(
    event_id: int,
    bankroll: float = Query(1000, gt=0),
    fast: bool = Query(False),
):
    """Retorna advice in-play para um evento de basquete Superbet (NBA)."""
    try:
        payload = await asyncio.to_thread(
            run_basket_live_advice,
            event_id,
            bankroll=bankroll,
            save_bronze=not fast,
            fast=fast,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return BasketSuperbetLiveAdviceResponse(**payload)


@router.get("/superbet/live/{event_id}/copilot", response_model=LiveCopilotResponse)
async def basket_superbet_live_copilot(
    event_id: int,
    bankroll: float = Query(1000, gt=0),
    fast: bool = Query(True),
):
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event
    from models.live_llm_copilot import run_live_copilot

    advice = get_stale_advice_for_event(event_id)
    if advice is None:
        try:
            advice = await asyncio.to_thread(
                run_basket_live_advice,
                event_id,
                bankroll=bankroll,
                save_bronze=False,
                fast=fast,
            )
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = await asyncio.to_thread(run_live_copilot, advice, sport="basketball")
    return LiveCopilotResponse(**payload)


@router.post("/superbet/live/{event_id}/copilot/agent", response_model=LiveCopilotAgentResponse)
async def basket_superbet_live_copilot_agent(event_id: int, req: LiveCopilotAgentRequest):
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event
    from models.live_copilot_agent import run_live_copilot_agent

    advice = get_stale_advice_for_event(event_id)
    if advice is None:
        try:
            advice = await asyncio.to_thread(
                run_basket_live_advice,
                event_id,
                bankroll=req.bankroll,
                save_bronze=False,
                fast=req.fast,
            )
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    history = [{"role": m.role, "content": m.content} for m in req.history]
    payload = await asyncio.to_thread(
        run_live_copilot_agent,
        advice,
        sport="basketball",
        message=req.message,
        history=history,
    )
    return LiveCopilotAgentResponse(**payload)
