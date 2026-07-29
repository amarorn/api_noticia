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
    LiveCopilotAgentRequest,
    LiveCopilotAgentResponse,
    LiveCopilotResponse,
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
    market: str | None = Query(None),
    outcome: str | None = Query(None),
    stake: float | None = Query(None, gt=0),
    odds_placed: float | None = Query(None, gt=1),
    fast: bool = Query(False),
):
    """Retorna advice in-play para um evento de beisebol Superbet."""
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
            run_baseball_live_advice,
            event_id,
            bankroll=bankroll,
            save_bronze=not fast,
            save_tick=not fast,
            fast=fast,
            user_bet=user_bet,
        )
    except SuperbetClientError as exc:
        from ingest.superbet.live_advice_cache import get_stale_advice_for_event

        advice = get_stale_advice_for_event(event_id)
        if advice is None:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        advice = dict(advice)
        advice["superbet_stale"] = True
        advice["superbet_error"] = str(exc)
        return BaseballSuperbetLiveAdviceResponse(**advice)

    return BaseballSuperbetLiveAdviceResponse(**payload)


@router.get("/superbet/live/{event_id}/copilot", response_model=LiveCopilotResponse)
async def baseball_superbet_live_copilot(
    event_id: int,
    bankroll: float = Query(1000, gt=0),
    fast: bool = Query(True),
):
    """Narrativa copiloto in-play para beisebol."""
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event
    from models.live_llm_copilot import run_live_copilot

    advice = get_stale_advice_for_event(event_id)
    if advice is None:
        try:
            advice = await asyncio.to_thread(
                run_baseball_live_advice,
                event_id,
                bankroll=bankroll,
                save_bronze=False,
                save_tick=False,
                fast=fast,
            )
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = await asyncio.to_thread(run_live_copilot, advice, sport="baseball")
    return LiveCopilotResponse(**payload)


@router.post("/superbet/live/{event_id}/copilot/agent", response_model=LiveCopilotAgentResponse)
async def baseball_superbet_live_copilot_agent(event_id: int, req: LiveCopilotAgentRequest):
    """Agente copiloto in-play para beisebol."""
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event
    from models.live_copilot_agent import run_live_copilot_agent

    advice = get_stale_advice_for_event(event_id)
    if advice is None:
        try:
            advice = await asyncio.to_thread(
                run_baseball_live_advice,
                event_id,
                bankroll=req.bankroll,
                save_bronze=False,
                save_tick=False,
                fast=req.fast,
            )
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    history = [{"role": m.role, "content": m.content} for m in req.history]
    payload = await asyncio.to_thread(
        run_live_copilot_agent,
        advice,
        sport="baseball",
        message=req.message,
        history=history,
    )
    return LiveCopilotAgentResponse(**payload)
