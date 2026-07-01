"""Rotas de apostas do usuário: open bets, settled bets, performance, observabilidade."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

import api.deps as deps
from schemas.user_bet import CheckAgainstModelRequest, SettledBetsBatchRequest, UserOpenBetRequest

router = APIRouter()


@router.post("/user/open-bets", response_model=dict)
def register_open_bet(req: UserOpenBetRequest):
    import uuid

    from api.user_bets_store import add_open_bet, list_combo_proposals, list_open_bets
    from models.bet_guardrails import BetGuardrailError, resolve_live_minute
    from models.combo_proposal import ComboProposalValidationError, validate_combo_proposal

    bet_id = req.id or str(uuid.uuid4())
    pick_dicts = [p.model_dump(exclude_none=True) for p in req.picks]
    is_proposal = req.source == "bolao_proposal"

    if is_proposal:
        try:
            validate_combo_proposal(req)
        except ComboProposalValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    minute = resolve_live_minute(
        minute=req.minute,
        superbet_event_id=req.superbet_event_id,
        home_team=req.home_team,
        away_team=req.away_team,
    )

    multipla_meta: dict[str, Any] = {}
    if len(req.picks) >= 2:
        from models.super_multipla import enrich_open_bet_with_super_multipla
        multipla_meta = enrich_open_bet_with_super_multipla(req)

    try:
        ub = add_open_bet(
            {
                "id": bet_id,
                "superbet_event_id": req.superbet_event_id,
                "event_name": req.event_name,
                "home_team": req.home_team,
                "away_team": req.away_team,
                "picks": pick_dicts,
                "stake": req.stake,
                "odds_placed": multipla_meta.get("total_odds", req.odds_placed),
                "potential_return": multipla_meta.get("potential_payout", req.potential_return),
                "cashout_value": req.cashout_value,
                "ticket_code": req.ticket_code,
                "status": "proposal" if is_proposal else "open",
                "source": req.source,
                "captured_at": req.captured_at or __import__("datetime", fromlist=["datetime"]).datetime.now().isoformat(),
                "model_source": req.model_source,
                "combined_ev": multipla_meta.get("combined_ev", req.combined_ev),
                "combined_prob": multipla_meta.get("combined_prob", req.combined_prob),
                "bonus_eligible": multipla_meta.get("bonus_eligible", req.bonus_eligible),
                "bonus_percentage": multipla_meta.get("bonus_percentage", req.bonus_percentage),
                "final_payout": multipla_meta.get("final_payout", req.final_payout),
                "proposal_minute": minute if is_proposal else None,
                "register_minute": minute if not is_proposal else None,
            },
            minute=minute,
            skip_guardrails=is_proposal,
        )
    except BetGuardrailError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc

    return {
        "id": ub.id,
        "message": "Proposta enviada à estação" if is_proposal else "Aposta cadastrada com sucesso",
        "status": ub.status, "event_name": ub.event_name,
        "picks_count": len(ub.picks), "stake": ub.stake,
        "odds_placed": ub.odds_placed, "bonus_eligible": ub.bonus_eligible,
        "bonus_percentage": ub.bonus_percentage, "final_payout": ub.final_payout,
        "open_bets_count": len(list_open_bets()),
        "proposals_count": len(list_combo_proposals()),
    }


@router.post("/user/bets/check-against-model", response_model=dict)
def check_bet_against_model(req: CheckAgainstModelRequest):
    from models.wc_against_model import check_single_bet_against_model

    predictor = deps.get_wc_predictor()
    alert = check_single_bet_against_model(
        predictor=predictor, market=req.market, outcome=req.outcome,
        home_team=req.home_team, away_team=req.away_team,
        superbet_event_id=req.superbet_event_id, phase=req.phase,
        stake=req.stake, odds_placed=req.odds_placed,
    )
    return {
        "against_model": alert is not None,
        "alert": alert,
        "message": alert["message"] if alert else "Palpite alinhado ao modelo",
    }


@router.post("/user/open-bets/dedupe", response_model=dict)
def dedupe_user_open_bets():
    from api.user_bets_store import dedupe_open_bets_store, list_open_bets

    stats = dedupe_open_bets_store()
    return {"message": "Deduplicação concluída", **stats, "open_bets_count": len(list_open_bets())}


@router.get("/user/open-bets", response_model=dict)
def list_user_open_bets(include_proposals: bool = True):
    from api.user_bets_store import list_combo_proposals, list_open_bets

    bets = list_open_bets()
    if include_proposals:
        bets = [*bets, *list_combo_proposals()]
    return {
        "count": len(bets),
        "bets": [
            {
                "id": b.id, "event_name": b.event_name,
                "home_team": b.home_team, "away_team": b.away_team,
                "picks": [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in b.picks],
                "stake": b.stake, "odds_placed": b.odds_placed,
                "potential_return": b.potential_return, "cashout_value": b.cashout_value,
                "bonus_eligible": b.bonus_eligible, "bonus_percentage": b.bonus_percentage,
                "final_payout": b.final_payout, "ticket_code": b.ticket_code,
                "status": b.status, "source": b.source, "captured_at": b.captured_at,
            }
            for b in bets
        ],
    }


@router.post("/user/open-bets/refresh-cashouts", response_model=dict)
def refresh_user_open_bets_cashouts(event_id: int | None = None):
    from api.user_bets_store import refresh_open_bets_cashouts

    summary = refresh_open_bets_cashouts(event_id=event_id)
    return {"message": "Cash-out atualizado", **summary}


@router.post("/user/settled-bets/batch", response_model=dict)
def register_settled_bets_batch(req: SettledBetsBatchRequest):
    from api.user_bets_store import add_settled_bets_batch

    bets_data = [b.model_dump(mode="json") for b in req.bets]
    for bd in bets_data:
        bd["picks"] = [p if isinstance(p, dict) else p.model_dump() for p in bd.get("picks", [])]
    added = add_settled_bets_batch(bets_data)
    return {"added": added, "total_received": len(req.bets), "message": f"{added} apostas novas"}


@router.get("/user/settled-bets", response_model=dict)
def list_user_settled_bets():
    from api.user_bets_store import list_settled_bets

    bets = list_settled_bets()
    return {"count": len(bets), "bets": [b.model_dump(mode="json") for b in bets]}


@router.get("/user/bets/query", response_model=dict)
def query_user_bets(
    min_score: int = Query(0, ge=0, le=100),
    max_results: int = Query(50, ge=1, le=200),
):
    from models.bet_query import bet_query_to_dict, query_bets

    result = query_bets(min_score=min_score, max_results=max_results)
    return {"error": None, "result": bet_query_to_dict(result), "message": "ok"}


@router.get("/user/bets/query/patterns", response_model=dict)
def get_user_bet_patterns():
    from models.bet_query import _analyze_user_patterns, _load_settled_bets

    settled = _load_settled_bets()
    patterns = _analyze_user_patterns(settled)
    return {"patterns": patterns, "n_settled": len(settled)}


@router.post("/user/bets/simulate", response_model=dict)
def simulate_user_bet(req: UserOpenBetRequest):
    from models.bet_simulator import simulate_bet, simulation_result_to_dict

    result = simulate_bet(
        picks=[p.model_dump() for p in req.picks],
        stake=req.stake, odds_placed=req.odds_placed,
        event_name=req.event_name, home_team=req.home_team,
        away_team=req.away_team, minute=req.minute,
        superbet_event_id=req.superbet_event_id,
    )
    return {"error": None, "result": simulation_result_to_dict(result), "message": "ok"}


@router.get("/user/bet-performance", response_model=dict)
def get_user_bet_performance():
    from api.user_bets_store import list_settled_bets
    from models.bet_observability import update_roi_by_market
    from models.wc_bet_performance import analyze_performance, performance_report_to_dict

    settled = list_settled_bets()
    bets_data = [b.model_dump(mode="json") for b in settled]
    report = analyze_performance(bets_data)
    update_roi_by_market({m.market: m.roi_pct for m in report.by_market})
    return {"error": None, "report": performance_report_to_dict(report)}


@router.get("/observability/bets")
def bet_observability_metrics():
    from models.bet_observability import get_bet_observability_metrics

    return get_bet_observability_metrics()
