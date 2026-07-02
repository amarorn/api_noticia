"""Rotas ao vivo: Superbet live, advice, inplay, handicap, bet builder."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

import api.deps as deps
from api.schemas import (
    BetBuilderValidateRequest,
    BetBuilderValidateResponse,
    HandicapAnalysisResponse,
    LiveCopilotAgentRequest,
    LiveCopilotAgentResponse,
    LiveCopilotResponse,
    WcBetAdviceRequest,
    WcBetAdviceResponse,
    WcInPlayRequest,
    WcInPlayResponse,
    WcSuperbetEventResponse,
    WcSuperbetLiveAdviceResponse,
    WcSuperbetLiveEventResponse,
    WcSuperbetLiveResponse,
    WcSuperbetPostmortemResponse,
)
from schemas.national_teams import normalize_national_team
from schemas.super_multipla import SuperMultiplaCalculateRequest, SuperMultiplaCalculateResponse

router = APIRouter(prefix="/worldcup")


# ---------------------------------------------------------------------------
# Superbet Live
# ---------------------------------------------------------------------------


@router.get("/superbet/live", response_model=WcSuperbetLiveResponse)
def worldcup_superbet_live(
    sport_id: int = Query(5),
    all_sports: bool = Query(False),
    rank: bool = Query(True),
):
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.live_rank import rank_live_events

    filter_sport = None if all_sports else sport_id
    try:
        events = SuperbetClient().fetch_live_events(sport_id=filter_sport)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    captured_at = datetime.now(UTC).isoformat()
    if rank:
        ranked = rank_live_events(events)
        payload = [
            WcSuperbetLiveEventResponse(**{**event.to_dict(), **bet_rank.to_dict()})
            for event, bet_rank in ranked
        ]
    else:
        payload = [WcSuperbetLiveEventResponse(**event.to_dict()) for event in events]

    return WcSuperbetLiveResponse(count=len(payload), sport_id=filter_sport, events=payload, captured_at=captured_at)


@router.get("/superbet/live/best-picks")
async def worldcup_superbet_live_best_picks(
    min_ev: float = Query(0.05),
    min_confidence: float = Query(0.0),
    max_picks_per_game: int = Query(3, ge=1, le=10),
    max_minute: int = Query(85),
    compute_missing: bool = Query(False),
    max_compute: int = Query(6, ge=1, le=15),
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
):
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event, list_cached_event_ids

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        live_events = SuperbetClient().fetch_live_events(sport_id=5)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=f"Superbet offline: {exc}") from exc

    cached_ids = set(list_cached_event_ids())
    advices: list[tuple[dict, dict]] = []
    to_compute: list[tuple[dict, int]] = []

    for ev in live_events:
        event_id = ev.event_id
        minute = getattr(getattr(ev, "inplay", None), "minute", 0) or 0
        if minute > max_minute:
            continue
        cached = get_stale_advice_for_event(event_id)
        if cached is not None:
            advices.append((ev.to_dict(), cached))
        elif compute_missing:
            to_compute.append((ev.to_dict(), event_id))

    to_compute = to_compute[:max_compute]
    if to_compute:
        async def _compute_one(ev_dict: dict, event_id: int) -> tuple[dict, dict] | None:
            try:
                payload = await asyncio.wait_for(
                    asyncio.to_thread(
                        run_live_advice, event_id, predictor,
                        phase=phase, bankroll=bankroll, fast=True,
                        save_bronze=False, save_tick=False, use_sofascore_live=False,
                    ),
                    timeout=20.0,
                )
                return (ev_dict, payload)
            except Exception:
                return None

        results = await asyncio.gather(*[_compute_one(ed, eid) for ed, eid in to_compute])
        advices.extend(r for r in results if r is not None)

    captured_at = datetime.now(UTC).isoformat()
    picks: list[dict] = []

    for ev_dict, advice in advices:
        aportes = advice.get("aportes") or []
        conf_score = (advice.get("confidence") or {}).get("score", 0.0)
        conf_label = (advice.get("confidence") or {}).get("label", "")
        home = advice.get("home_team") or ev_dict.get("home_team", "")
        away = advice.get("away_team") or ev_dict.get("away_team", "")
        minute = advice.get("minute", 0) or 0
        score = advice.get("current_score", "0x0") or "0x0"
        event_id = ev_dict.get("event_id")

        if conf_score < min_confidence:
            continue

        count = 0
        for a in aportes:
            ev_val = float(a.get("expected_value") or 0)
            if ev_val < min_ev or a.get("action") not in ("apostar", "aporte"):
                continue
            picks.append({
                "event_id": event_id, "home": home, "away": away, "minute": minute,
                "score": score, "market": a.get("market", ""), "outcome": a.get("outcome", ""),
                "label": a.get("label", ""),
                "model_prob": round(float(a.get("model_prob") or 0), 4),
                "market_odd": round(float(a.get("market_odd") or 0), 2),
                "fair_odd": round(1 / float(a.get("model_prob") or 1), 2) if a.get("model_prob") else None,
                "ev_pct": round(ev_val * 100, 1),
                "edge_pp": round(float(a.get("edge_pp") or 0), 1),
                "kelly_quarter": round(float(a.get("kelly_quarter") or 0), 4),
                "suggested_stake_value": a.get("suggested_stake_value"),
                "confidence_score": round(conf_score, 3), "confidence_label": conf_label,
                "from_cache": event_id in cached_ids, "captured_at": captured_at,
            })
            count += 1
            if count >= max_picks_per_game:
                break

    picks.sort(key=lambda p: p["ev_pct"], reverse=True)
    return {"count": len(picks), "games_analyzed": len(advices), "captured_at": captured_at, "picks": picks}


@router.get("/superbet/live/{event_id}/advice", response_model=WcSuperbetLiveAdviceResponse)
async def worldcup_superbet_live_advice(
    event_id: int,
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
    market: str | None = Query(None),
    outcome: str | None = Query(None),
    stake: float | None = Query(None, gt=0),
    odds_placed: float | None = Query(None, gt=1),
    fast: bool = Query(False),
    kickoff: str | None = Query(None),
):
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_bet_advice import UserBetInput

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_bet = None
    if market and outcome and stake is not None and odds_placed is not None:
        user_bet = UserBetInput(market=market, outcome=outcome, stake=stake, odds_placed=odds_placed)

    try:
        payload = await asyncio.to_thread(
            run_live_advice, event_id, predictor,
            phase=phase, bankroll=bankroll, user_bet=user_bet,
            save_bronze=not fast, save_tick=not fast,
            use_sofascore_live=False if fast else None, fast=fast, kickoff=kickoff,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WcSuperbetLiveAdviceResponse(**payload)


@router.get("/superbet/live/{event_id}/copilot", response_model=LiveCopilotResponse)
async def worldcup_superbet_live_copilot(
    event_id: int,
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
    fast: bool = Query(True),
    kickoff: str | None = Query(None),
):
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event
    from models.live_llm_copilot import run_live_copilot

    advice = get_stale_advice_for_event(event_id)
    if advice is None:
        try:
            predictor = deps.get_wc_predictor()
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            advice = await asyncio.to_thread(
                run_live_advice,
                event_id,
                predictor,
                phase=phase,
                bankroll=bankroll,
                save_bronze=False,
                save_tick=False,
                use_sofascore_live=False,
                fast=fast,
                kickoff=kickoff,
            )
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload = await asyncio.to_thread(run_live_copilot, advice, sport="football")
    return LiveCopilotResponse(**payload)


@router.get("/superbet/live/{event_id}/copilot/latest", response_model=LiveCopilotResponse)
async def worldcup_superbet_live_copilot_latest(event_id: int):
    """Retorna último copiloto em cache (sem recomputar GPT)."""
    from config import settings
    from models.live_copilot_cache import get_stale_copilot_for_event

    stale = get_stale_copilot_for_event(
        event_id,
        max_age_sec=float(settings.live_copilot_cache_ttl_sec),
    )
    if stale is None:
        raise HTTPException(status_code=404, detail="Copiloto ainda não disponível para este evento.")
    stale["cached"] = True
    return LiveCopilotResponse(**stale)


async def _load_football_advice_for_copilot(
    event_id: int,
    *,
    phase: str,
    bankroll: float,
    fast: bool,
    kickoff: str | None,
) -> dict:
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from ingest.superbet.live_advice_cache import get_stale_advice_for_event

    advice = get_stale_advice_for_event(event_id)
    if advice is not None:
        return advice

    predictor = deps.get_wc_predictor()
    try:
        return await asyncio.to_thread(
            run_live_advice,
            event_id,
            predictor,
            phase=phase,
            bankroll=bankroll,
            save_bronze=False,
            save_tick=False,
            use_sofascore_live=False,
            fast=fast,
            kickoff=kickoff,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/superbet/live/{event_id}/copilot/agent", response_model=LiveCopilotAgentResponse)
async def worldcup_superbet_live_copilot_agent(event_id: int, req: LiveCopilotAgentRequest):
    """Copiloto modo agente — LLM consulta tools sobre o advice quantitativo."""
    from models.live_copilot_agent import run_live_copilot_agent

    try:
        advice = await _load_football_advice_for_copilot(
            event_id,
            phase=req.phase,
            bankroll=req.bankroll,
            fast=req.fast,
            kickoff=req.kickoff,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    history = [{"role": m.role, "content": m.content} for m in req.history]
    payload = await asyncio.to_thread(
        run_live_copilot_agent,
        advice,
        sport="football",
        message=req.message,
        history=history,
    )
    return LiveCopilotAgentResponse(**payload)


@router.post("/superbet/live/{event_id}/context")
async def upload_match_context(event_id: int, file: UploadFile = File(...)):
    from ingest.superbet.match_context_parser import parse_match_context
    from ingest.superbet.match_context_store import save_match_context

    content_bytes = await file.read()
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = content_bytes.decode("latin-1", errors="replace")

    ctx = parse_match_context(text, filename=file.filename or "")
    data = ctx.to_dict()
    data["source_filename"] = file.filename or ""
    save_match_context(event_id, data)

    return {
        "event_id": event_id, "extracted": data, "notes": ctx.notes,
        "message": f"Contexto salvo — {len(ctx.notes)} enriquecimento(s) ativo(s) para o evento {event_id}.",
    }


@router.get("/superbet/live/{event_id}/context")
async def get_live_match_context(event_id: int):
    from ingest.superbet.match_context_store import load_match_context

    data = load_match_context(event_id)
    return {"event_id": event_id, "context": data}


@router.delete("/superbet/live/{event_id}/context")
async def delete_match_context(event_id: int):
    from ingest.superbet.match_context_store import delete_match_context as _delete

    removed = _delete(event_id)
    return {"event_id": event_id, "removed": removed}


@router.post("/superbet/live/{event_id}/fetch-context")
async def fetch_context_via_perplexity(
    event_id: int,
    home_team: str,
    away_team: str,
    force_refresh: bool = False,
):
    from ingest.research.perplexity_client import PerplexityError, search_inplay_context
    from ingest.superbet.match_context_parser import parse_match_context
    from ingest.superbet.match_context_store import load_match_context, save_match_context

    from config import settings

    if not force_refresh:
        existing = load_match_context(event_id)
        if existing:
            existing["from_cache"] = True
            return existing

    if not settings.perplexity_api_key:
        raise HTTPException(status_code=503, detail="PERPLEXITY_API_KEY não configurada no servidor.")

    try:
        result = await asyncio.to_thread(search_inplay_context, home_team, away_team)
    except PerplexityError as exc:
        raise HTTPException(status_code=502, detail=f"Perplexity: {exc}") from exc

    raw_text = result["text"]
    ctx = parse_match_context(raw_text, filename=f"perplexity_{event_id}")
    ctx_dict = ctx.to_dict()
    ctx_dict["perplexity_citations"] = result.get("citations", [])
    ctx_dict["perplexity_model"] = result.get("model", "")
    ctx_dict["raw_text"] = raw_text
    ctx_dict["from_cache"] = False
    save_match_context(event_id, ctx_dict)
    return ctx_dict


@router.get("/superbet/live/{event_id}/optimized-tickets")
async def worldcup_superbet_optimized_tickets(
    event_id: int,
    phase: str = Query("friendly"),
    bankroll: float = Query(1000, gt=0),
    max_legs: int = Query(4, ge=2, le=6),
    min_legs: int = Query(2, ge=2, le=4),
    top_k: int = Query(5, ge=1, le=10),
    fast: bool = Query(False),
):
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_combo_optimizer import build_optimized_tickets, tickets_to_dict

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        payload = await asyncio.to_thread(
            run_live_advice, event_id, predictor,
            phase=phase, bankroll=bankroll,
            save_bronze=not fast, save_tick=not fast,
            use_sofascore_live=False if fast else None, fast=fast,
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
        market_scan, minute=minute, home_score=home_score, away_score=away_score,
        bankroll=bankroll, max_legs=max_legs, min_legs=min_legs, top_k=top_k,
    )

    td = tickets_to_dict(tickets_by_period)
    return {
        "event_id": str(event_id),
        "home_team": payload["home_team"], "away_team": payload["away_team"],
        "minute": minute, "home_score": home_score, "away_score": away_score,
        "tickets_1h": td.get("1h", []), "tickets_2h": td.get("2h", []),
        "tickets_ft": td.get("ft", []), "tickets_mixed": td.get("mixed", []),
        "total_tickets": sum(len(td.get(k, [])) for k in ("1h", "2h", "ft", "mixed")),
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Superbet Events
# ---------------------------------------------------------------------------


@router.get("/superbet/events/{event_id}", response_model=WcSuperbetEventResponse)
async def worldcup_superbet_event(event_id: int, merge_odds: bool = False, save_bronze: bool = True):
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import fetch_event_with_stale_fallback, merge_snapshot_into_odds_file, save_event_snapshot

    client = SuperbetClient()
    try:
        snapshot, superbet_stale = await asyncio.to_thread(fetch_event_with_stale_fallback, client, event_id)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if save_bronze and not superbet_stale:
        await asyncio.to_thread(save_event_snapshot, snapshot)
    if merge_odds and snapshot.h2h_odds:
        await asyncio.to_thread(merge_snapshot_into_odds_file, snapshot)
        from pipelines.wc_market_features import load_match_odds_index
        load_match_odds_index.cache_clear()

    payload = snapshot.to_dict()
    payload["superbet_stale"] = superbet_stale
    return WcSuperbetEventResponse(**payload)


@router.get("/superbet/events/{event_id}/postmortem", response_model=WcSuperbetPostmortemResponse)
async def worldcup_superbet_event_postmortem(
    event_id: int,
    regenerate: bool = Query(False),
):
    from pipelines.inplay_postmortem import get_or_build_inplay_postmortem

    report = await asyncio.to_thread(get_or_build_inplay_postmortem, event_id, regenerate=regenerate)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Post-mortem não encontrado para evento {event_id}")
    return WcSuperbetPostmortemResponse(**report)


@router.post("/superbet/validate-builder", response_model=BetBuilderValidateResponse)
def worldcup_superbet_validate_builder(req: BetBuilderValidateRequest):
    from models.inplay_bet_builder_guard import validate_bet_builder

    legs = [leg.model_dump() for leg in req.legs]
    result = validate_bet_builder(
        legs, minute=req.minute, home_score=req.home_score, away_score=req.away_score,
        ht_home=req.ht_home_score, ht_away=req.ht_away_score, combined_odd=req.combined_odd,
    )
    return BetBuilderValidateResponse(**result)


@router.post("/superbet/multiple/calculate", response_model=SuperMultiplaCalculateResponse)
def worldcup_superbet_multiple_calculate(req: SuperMultiplaCalculateRequest):
    from models.super_multipla import SuperMultiplaValidationError, calculate_super_multipla

    try:
        return calculate_super_multipla(req)
    except SuperMultiplaValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc


# ---------------------------------------------------------------------------
# Handicap / InPlay / Bet Advice
# ---------------------------------------------------------------------------


@router.get("/handicap/{event_id}")
def worldcup_handicap_analysis(
    event_id: int,
    bankroll: float = Query(default=1000.0, ge=10.0),
    phase: str = Query(default="group"),
):
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
    from models.wc_handicap_analysis import build_handicap_analysis
    from models.wc_inplay import inplay_from_predictor

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        snapshot, _stale = fetch_event_with_stale_fallback(SuperbetClient(), event_id)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_event_snapshot(snapshot)
    home = normalize_national_team(snapshot.home_team)
    away = normalize_national_team(snapshot.away_team)

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score, away_score, minute = ip.home_score, ip.away_score, ip.minute
        ht_h, ht_a = ip.ht_home_score, ip.ht_away_score
    else:
        home_score = away_score = minute = 0
        ht_h = ht_a = None

    result = inplay_from_predictor(
        predictor, home_team=home, away_team=away,
        home_score=home_score, away_score=away_score, minute=minute,
        phase=phase, is_neutral=True, ht_home_score=ht_h, ht_away_score=ht_a,
    )
    payload = build_handicap_analysis(
        event_id=event_id, home_team=home, away_team=away,
        current_score=f"{home_score}x{away_score}", minute=minute,
        model_probs=result.handicap_probs, snapshot=snapshot,
        bankroll=bankroll, phase=phase,
    )
    return HandicapAnalysisResponse(**payload)


@router.post("/inplay", response_model=WcInPlayResponse)
def worldcup_inplay(req: WcInPlayRequest):
    from ingest.superbet.benchmark import market_benchmark
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import merge_snapshot_into_odds_file, save_event_snapshot
    from models.wc_inplay import inplay_from_predictor
    from models.wc_market_shrinkage import market_probs_from_h2h_implied

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home = normalize_national_team(req.home_team)
    away = normalize_national_team(req.away_team)
    home_score, away_score, minute = req.home_score, req.away_score, req.minute
    ht_home, ht_away = req.ht_home_score, req.ht_away_score
    superbet_snapshot = None
    benchmark = None

    if req.superbet_event_id is not None:
        try:
            superbet_snapshot = SuperbetClient().fetch_event(req.superbet_event_id)
            save_event_snapshot(superbet_snapshot)
            if req.merge_superbet_odds and superbet_snapshot.h2h_odds:
                merge_snapshot_into_odds_file(superbet_snapshot)
                from pipelines.wc_market_features import load_match_odds_index
                load_match_odds_index.cache_clear()
            if superbet_snapshot.inplay:
                home_score = superbet_snapshot.inplay.home_score
                away_score = superbet_snapshot.inplay.away_score
                minute = superbet_snapshot.inplay.minute
                if superbet_snapshot.inplay.ht_home_score is not None:
                    ht_home = superbet_snapshot.inplay.ht_home_score
                    ht_away = superbet_snapshot.inplay.ht_away_score
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    market_probs = None
    if superbet_snapshot is not None:
        market_probs = market_probs_from_h2h_implied(superbet_snapshot.h2h_implied)

    result = inplay_from_predictor(
        predictor, home_team=home, away_team=away,
        home_score=home_score, away_score=away_score, minute=minute,
        phase=req.phase, is_neutral=True, match_minutes=req.match_minutes,
        ht_home_score=ht_home, ht_away_score=ht_away, market_probs=market_probs,
    )
    payload = result.to_dict()
    if superbet_snapshot and superbet_snapshot.h2h_implied:
        benchmark = market_benchmark(
            superbet_snapshot,
            model_h2h={"1": payload["prob_final_home"], "X": payload["prob_final_draw"], "2": payload["prob_final_away"]},
            model_totals=payload.get("final_line_probs"),
        )
    payload["market_benchmark"] = benchmark
    payload["superbet"] = superbet_snapshot.to_dict() if superbet_snapshot else None
    return WcInPlayResponse(**payload)


@router.post("/bet/advice", response_model=WcBetAdviceResponse)
def worldcup_bet_advice(req: WcBetAdviceRequest):
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_bet_advice import UserBetInput

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_bet = None
    if req.user_bet is not None:
        user_bet = UserBetInput(
            market=req.user_bet.market, outcome=req.user_bet.outcome,
            stake=req.user_bet.stake, odds_placed=req.user_bet.odds_placed,
        )

    try:
        payload = run_live_advice(
            req.superbet_event_id, predictor,
            phase=req.phase, bankroll=req.bankroll, user_bet=user_bet,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WcBetAdviceResponse(
        home_team=payload["home_team"], away_team=payload["away_team"],
        minute=payload["minute"], current_score=payload.get("current_score"),
        cashout=payload.get("cashout"), aportes=payload.get("aportes", []),
        inplay_summary=payload.get("inplay_summary", {}),
        superbet_event_id=req.superbet_event_id,
    )
