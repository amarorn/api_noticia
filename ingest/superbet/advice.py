"""Orquestra Superbet ao vivo → modelo in-play → cash-out / aportes."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from ingest.superbet.benchmark import h2h_overround, market_benchmark
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.live_ticks import append_live_tick
from ingest.superbet.parser import SuperbetEventSnapshot
from ingest.superbet.store import save_event_snapshot
from models.wc_bet_advice import UserBetInput, build_bet_advice_report
from models.wc_bet_strategy import build_bet_strategy_report
from models.wc_inplay import inplay_from_predictor
from schemas.national_teams import normalize_national_team

_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}


def run_live_advice(
    event_id: int,
    predictor: Any,
    *,
    phase: str = "friendly",
    bankroll: float = 1000.0,
    user_bet: UserBetInput | None = None,
    save_bronze: bool = True,
    save_tick: bool = True,
    client: SuperbetClient | None = None,
) -> dict[str, Any]:
    superbet_client = client or SuperbetClient()
    snapshot = superbet_client.fetch_event(event_id)
    if save_bronze:
        save_event_snapshot(snapshot)

    home = normalize_national_team(snapshot.home_team)
    away = normalize_national_team(snapshot.away_team)

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score, away_score, minute = ip.home_score, ip.away_score, ip.minute
        ht_h, ht_a = ip.ht_home_score, ip.ht_away_score
        status = ip.status
        period_label = ip.period_label
    else:
        home_score = away_score = minute = 0
        ht_h = ht_a = None
        status = None
        period_label = None

    result = inplay_from_predictor(
        predictor,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        phase=phase,
        is_neutral=True,
        ht_home_score=ht_h,
        ht_away_score=ht_a,
    )
    inplay_dict = result.to_dict()
    report = build_bet_advice_report(
        home_team=home,
        away_team=away,
        inplay=inplay_dict,
        snapshot=snapshot,
        user_bet=user_bet,
        minute=minute,
        bankroll=bankroll,
    )

    snapshot_dict = snapshot.to_dict()
    if save_tick:
        try:
            append_live_tick(
                event_id=event_id,
                snapshot=snapshot_dict,
                inplay=inplay_dict,
                advice=report,
            )
        except Exception as exc:
            logger.warning("Falha ao gravar live_ticks parquet (event_id=%s): %s", event_id, exc)

    is_finished = str(status or "").upper() in _FINISHED_STATUSES

    model_h2h = {
        "1": float(inplay_dict.get("prob_final_home") or 0),
        "X": float(inplay_dict.get("prob_final_draw") or 0),
        "2": float(inplay_dict.get("prob_final_away") or 0),
    }
    model_totals = {
        k: float(v)
        for k, v in (inplay_dict.get("final_line_probs") or {}).items()
        if isinstance(v, (int, float))
    }
    benchmark = None
    if snapshot.h2h_implied:
        benchmark = market_benchmark(
            snapshot,
            model_h2h=model_h2h,
            model_totals=model_totals or None,
        )
    overround = h2h_overround(snapshot.h2h_odds)

    return {
        "home_team": home,
        "away_team": away,
        "minute": minute,
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label,
        "status": status,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
        "cashout": report.get("cashout"),
        "aportes": report.get("aportes", []),
        "inplay_summary": {
            "prob_final_home": inplay_dict.get("prob_final_home"),
            "prob_final_draw": inplay_dict.get("prob_final_draw"),
            "prob_final_away": inplay_dict.get("prob_final_away"),
            "over_2_5": inplay_dict.get("final_line_probs", {}).get("over_2_5"),
            "btts": inplay_dict.get("btts_final"),
            "prob_next_goal_home": inplay_dict.get("prob_next_goal_home"),
            "prob_next_goal_away": inplay_dict.get("prob_next_goal_away"),
            "prob_no_more_goals": inplay_dict.get("prob_no_more_goals"),
        },
        "superbet_event_id": event_id,
        "h2h_odds": snapshot.h2h_odds,
        "h2h_implied": snapshot.h2h_implied,
        "h2h_overround": overround,
        "generosity_probs": snapshot.generosity_probs,
        "market_benchmark": benchmark,
        "strategy": build_bet_strategy_report(
            home_team=home,
            away_team=away,
            inplay=inplay_dict,
            snapshot=snapshot,
            benchmark=benchmark,
            user_bet=user_bet,
            minute=minute,
            bankroll=bankroll,
            h2h_overround=overround,
        ),
        "captured_at": snapshot.captured_at,
        "betradar_id": snapshot.betradar_id,
        "raw_market_count": snapshot.raw_market_count,
        "btts_odds": snapshot.btts_odds,
        "next_goal_odds": snapshot.next_goal_odds,
        "analysis_coverage": {
            "h2h": bool(snapshot.h2h_odds),
            "totals": bool(snapshot.totals),
            "btts": bool(snapshot.btts_odds),
            "next_goal": bool(snapshot.next_goal_odds),
            "combos": list(snapshot.combo_markets.keys()),
        },
    }


__all__ = ["SuperbetClientError", "run_live_advice"]
