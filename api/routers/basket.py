"""Rotas ao vivo para basquete (NBA)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    BasketMultiGameTicketsRequest,
    BasketMultiGameTicketsResponse,
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


@router.post("/superbet/multi-game/tickets", response_model=BasketMultiGameTicketsResponse)
async def basket_superbet_multi_game_tickets(req: BasketMultiGameTicketsRequest):
    """Monta bilhetes cross-game: 1 palpite por jogo, odds/EV combinados (produto)."""
    from models.basket_multi_game_tickets import build_basket_multi_game_tickets

    unique_ids = list(dict.fromkeys(req.event_ids))
    if len(unique_ids) < 2:
        raise HTTPException(status_code=422, detail="Informe pelo menos 2 event_ids distintos.")

    advice_by_event: dict[int, dict] = {}
    errors: list[str] = []

    for event_id in unique_ids:
        try:
            advice = await asyncio.to_thread(
                run_basket_live_advice,
                event_id,
                bankroll=req.bankroll,
                save_bronze=False,
                fast=req.fast,
            )
        except SuperbetClientError as exc:
            errors.append(f"evento {event_id}: {exc}")
            continue
        advice_by_event[event_id] = advice

    if len(advice_by_event) < 2:
        detail = "Não foi possível obter advice de ao menos 2 jogos."
        if errors:
            detail += " " + "; ".join(errors)
        raise HTTPException(status_code=502, detail=detail)

    payload = build_basket_multi_game_tickets(
        advice_by_event,
        bankroll=req.bankroll,
        stake=req.stake,
        min_legs=req.min_legs,
        max_legs=req.max_legs,
        max_tickets=req.max_tickets,
        require_apostar=req.require_apostar,
    )
    return BasketMultiGameTicketsResponse(**payload)


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
