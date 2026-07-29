"""Orquestra Superbet ao vivo → modelo in-play de beisebol → advice."""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.event_finalize import maybe_finalize_finished_event
from ingest.superbet.live_advice_cache import (
    advice_cache_key,
    get_stale_advice_for_event,
    run_with_advice_cache,
)
from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
from models.baseball_benchmark import baseball_market_benchmark
from models.baseball_bet_advice import build_baseball_bet_advice_report
from models.baseball_bet_guardrails import build_baseball_bet_guardrails
from models.baseball_bet_strategy import build_baseball_bet_strategy_report
from models.baseball_cashout import advise_baseball_cashout, cashout_to_dict
from models.baseball_trend_advisor import build_baseball_trend_report
from models.wc_bet_advice import apply_trend_to_cashout
from models.baseball_dead_market import list_dead_market_flags
from models.baseball_game_phase import resolve_baseball_game_phase
from models.baseball_inplay import simulate_baseball_inplay
from models.wc_bet_advice import UserBetInput

logger = logging.getLogger(__name__)

_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}


def _match_is_finished(status: str | None, inning: int, match_innings: int = 9) -> bool:
    st = str(status or "").upper()
    if st in _FINISHED_STATUSES:
        return True
    if inning >= match_innings + 5:
        return True
    return False


def _build_baseball_advice_payload(
    *,
    event_id: int,
    snapshot: Any,
    superbet_stale: bool,
    bankroll: float,
    fast: bool,
    save_bronze: bool,
    save_tick: bool = True,
) -> dict[str, Any]:
    if save_bronze and not superbet_stale:
        try:
            save_event_snapshot(snapshot)
        except Exception as exc:
            logger.warning("Falha ao salvar snapshot de beisebol event_id=%s: %s", event_id, exc)

    sport_id = getattr(snapshot, "sport_id", None)
    if sport_id is None:
        sport_id = settings.baseball_sport_id
    if sport_id is not None and sport_id != settings.baseball_sport_id:
        logger.info(
            "baseball_advice_sport_id_inesperado event_id=%s sport_id=%s expected=%s",
            event_id,
            sport_id,
            settings.baseball_sport_id,
        )

    home_team = snapshot.home_team
    away_team = snapshot.away_team

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score = ip.home_score
        away_score = ip.away_score
        inning = max(1, ip.minute) if ip.minute > 0 else max(1, len(ip.baseball_innings) or 1)
        status = ip.status
        period_label = ip.period_label
        baseball_innings = ip.baseball_innings
    else:
        home_score = away_score = 0
        inning = 1
        status = None
        period_label = None
        baseball_innings = []

    total_runs_odds = snapshot.total_points_odds
    if not total_runs_odds and snapshot.inferred_total_runs is not None:
        line = snapshot.inferred_total_runs
        total_runs_odds = {f"{line:g}": {"over": 1.91, "under": 1.91}}

    inplay_result = simulate_baseball_inplay(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        match_innings=settings.baseball_match_innings,
        moneyline_odds=snapshot.moneyline_odds or snapshot.h2h_odds,
        spread_odds=snapshot.spread_odds,
        total_runs_odds=total_runs_odds,
        team_totals=snapshot.team_totals,
        period_markets=getattr(snapshot, "baseball_period_markets", None),
        innings_observed=baseball_innings,
        n_simulations=settings.baseball_fast_mc_simulations if fast else None,
    )
    inplay_dict = inplay_result.to_dict()

    report = build_baseball_bet_advice_report(
        inplay=inplay_result,
        snapshot=snapshot,
        bankroll=bankroll,
        baseball_innings=baseball_innings,
    )

    is_finished = _match_is_finished(
        status=status,
        inning=inning,
        match_innings=settings.baseball_match_innings,
    )

    game_phase = resolve_baseball_game_phase(
        inning=inning,
        home_score=home_score,
        away_score=away_score,
        is_finished=is_finished,
        match_innings=settings.baseball_match_innings,
    )

    model_ml = inplay_dict.get("moneyline_probs") or {
        "1": inplay_dict.get("prob_home_win"),
        "2": inplay_dict.get("prob_away_win"),
    }
    benchmark = None
    if snapshot.moneyline_implied or snapshot.h2h_implied:
        benchmark = baseball_market_benchmark(
            snapshot,
            model_moneyline={k: float(v) for k, v in model_ml.items() if v is not None},
            model_totals=inplay_dict.get("total_probs") or None,
            model_spread=inplay_dict.get("spread_probs") or None,
        )

    dead_flags = list_dead_market_flags(
        report["aportes"],
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        baseball_innings=baseball_innings,
    )

    strategy = build_baseball_bet_strategy_report(
        inplay=inplay_result,
        snapshot=snapshot,
        aportes=report["aportes"],
        game_phase=game_phase,
        benchmark=benchmark,
        baseball_innings=baseball_innings,
    )
    for warn in report.get("sanity_warnings") or []:
        strategy["shields"].append({
            "action": "evitar",
            "priority": "alta",
            "title": "Linha filtrada",
            "reason": warn,
        })

    bet_guardrails = build_baseball_bet_guardrails(
        game_phase=game_phase,
        dead_markets=dead_flags,
    )

    if save_tick and not superbet_stale:
        try:
            from ingest.superbet.live_ticks import append_live_tick

            tick_inplay = {
                **inplay_dict,
                "minute": inning,
                "prob_final_home": inplay_dict.get("prob_home_win"),
                "prob_final_draw": 0.0,
                "prob_final_away": inplay_dict.get("prob_away_win"),
            }
            snap_dict = snapshot.to_dict()
            if snap_dict.get("sport_id") is None:
                snap_dict["sport_id"] = sport_id
            append_live_tick(
                event_id=event_id,
                snapshot=snap_dict,
                inplay=tick_inplay,
                advice={"aportes": report["aportes"]},
            )
        except Exception as exc:
            logger.warning("Falha ao gravar live_ticks beisebol event_id=%s: %s", event_id, exc)

    trend_report = None
    if not fast:
        try:
            trend_report = build_baseball_trend_report(
                event_id=event_id,
                home_team=home_team,
                away_team=away_team,
                user_bet=None,
                event_snapshot_raw=snapshot.to_dict(),
            )
        except Exception as exc:
            logger.warning("Erro ao construir trend_report beisebol: %s", exc)

    from ingest.superbet.score_stale import detect_baseball_score_stale, load_last_live_tick

    score_stale_report = detect_baseball_score_stale(
        home_score=home_score,
        away_score=away_score,
        inning=inning,
        last_tick=load_last_live_tick(event_id) if not fast else None,
    )

    finalize_info = None
    if not fast and is_finished:
        finalize_info = maybe_finalize_finished_event(
            event_id=event_id,
            snapshot=snapshot,
            inplay={
                **inplay_dict,
                "current_score": inplay_dict.get("current_score"),
                "prob_final_home": inplay_dict.get("prob_home_win"),
                "prob_final_draw": 0.0,
                "prob_final_away": inplay_dict.get("prob_away_win"),
            },
            advice=report,
            is_finished=True,
        )

    return {
        "home_team": home_team,
        "away_team": away_team,
        "inning": inning,
        "minute": inning,
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label or f"{inning}I",
        "status": status,
        "baseball_innings": baseball_innings,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
        "score_stale": score_stale_report,
        "event_finalize": finalize_info,
        "superbet_stale": superbet_stale,
        "superbet_event_id": event_id,
        "sport_id": sport_id,
        "captured_at": snapshot.captured_at,
        "h2h_odds": snapshot.moneyline_odds or snapshot.h2h_odds,
        "h2h_implied": snapshot.moneyline_implied or snapshot.h2h_implied,
        "spread_odds": snapshot.spread_odds,
        "spread_implied": snapshot.spread_implied,
        "total_runs_odds": snapshot.total_points_odds,
        "total_runs_implied": snapshot.total_points_implied,
        "team_totals": snapshot.team_totals or {},
        "baseball_period_markets": getattr(snapshot, "baseball_period_markets", None) or {},
        "game_phase": game_phase.to_dict(),
        "market_benchmark": benchmark,
        "strategy": strategy,
        "bet_guardrails": bet_guardrails,
        "inplay_summary": {
            "prob_home_win": inplay_dict["prob_home_win"],
            "prob_away_win": inplay_dict["prob_away_win"],
            "expected_final_home": inplay_dict["expected_final_home"],
            "expected_final_away": inplay_dict["expected_final_away"],
            "expected_total": inplay_dict["expected_total"],
            "remaining_innings": inplay_dict["remaining_innings"],
            "moneyline_probs": inplay_dict["moneyline_probs"],
            "spread_probs": inplay_dict["spread_probs"],
            "total_probs": inplay_dict["total_probs"],
            "team_total_probs": inplay_dict["team_total_probs"],
            "period_probs": inplay_dict.get("period_probs", {}),
            "rpi_home": inplay_dict["rpi_home"],
            "rpi_away": inplay_dict["rpi_away"],
            "rpi_home_prior": inplay_dict["rpi_home_prior"],
            "rpi_away_prior": inplay_dict["rpi_away_prior"],
            "match_innings": inplay_dict["match_innings"],
            "n_simulations": inplay_dict["n_simulations"],
            "market_total_line": inplay_dict["market_total_line"],
            "market_spread_line": inplay_dict["market_spread_line"],
            "score_adapted": inplay_dict.get("score_adapted"),
            "obs_elapsed_innings": inplay_dict.get("obs_elapsed_innings"),
        },
        "aportes": report["aportes"],
        "confidence": report["confidence"],
        "trend_report": trend_report,
    }


def run_baseball_live_advice(
    event_id: int,
    *,
    bankroll: float = 1000.0,
    save_bronze: bool = True,
    save_tick: bool = True,
    fast: bool = False,
    user_bet: UserBetInput | None = None,
    client: SuperbetClient | None = None,
) -> dict[str, Any]:
    """Busca evento Superbet de beisebol e retorna advice in-play."""
    superbet_client = client or SuperbetClient()
    try:
        snapshot, superbet_stale = fetch_event_with_stale_fallback(superbet_client, event_id)
    except SuperbetClientError as exc:
        cached = get_stale_advice_for_event(event_id)
        if cached is None:
            raise
        cached = dict(cached)
        cached["superbet_stale"] = True
        cached["superbet_error"] = str(exc)
        return cached

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score = ip.home_score
        away_score = ip.away_score
        inning = max(1, ip.minute) if ip.minute > 0 else max(1, len(ip.baseball_innings) or 1)
    else:
        home_score = away_score = 0
        inning = 1

    cache_key = advice_cache_key(
        event_id=event_id,
        home_score=home_score,
        away_score=away_score,
        minute=inning,
        bankroll=bankroll,
        fast=fast,
        phase="baseball",
    )

    def _compute() -> dict[str, Any]:
        return _build_baseball_advice_payload(
            event_id=event_id,
            snapshot=snapshot,
            superbet_stale=superbet_stale,
            bankroll=bankroll,
            fast=fast,
            save_bronze=save_bronze,
            save_tick=save_tick,
        )

    payload = run_with_advice_cache(cache_key, _compute, fast=fast)
    if superbet_stale:
        payload = dict(payload)
        payload["superbet_stale"] = True

    if user_bet is not None:
        payload = dict(payload)
        summary = payload.get("inplay_summary") or {}
        cashout = advise_baseball_cashout(
            user_bet,
            summary,
            inning=int(payload.get("inning") or 1),
        )
        trend_report = payload.get("trend_report")
        if trend_report is None and not fast:
            try:
                trend_report = build_baseball_trend_report(
                    event_id=event_id,
                    home_team=str(payload.get("home_team") or ""),
                    away_team=str(payload.get("away_team") or ""),
                    user_bet={
                        "market": user_bet.market,
                        "outcome": user_bet.outcome,
                        "stake": user_bet.stake,
                        "odds_placed": user_bet.odds_placed,
                        "picks": [
                            {"market": user_bet.market, "outcome": user_bet.outcome},
                        ],
                    },
                    event_snapshot_raw=snapshot.to_dict(),
                )
            except Exception as exc:
                logger.warning("Erro ao construir trend_report beisebol: %s", exc)
        cashout = apply_trend_to_cashout(cashout, trend_report)
        cashout_dict = cashout_to_dict(cashout)
        payload["cashout"] = cashout_dict
        payload["trend_report"] = trend_report
        if payload.get("strategy") is not None:
            payload["strategy"] = dict(payload["strategy"])
            payload["strategy"]["cashout"] = cashout_dict

    return payload


__all__ = ["SuperbetClientError", "run_baseball_live_advice"]
