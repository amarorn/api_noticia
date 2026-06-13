"""Orquestra Superbet ao vivo → modelo in-play → cash-out / aportes."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ingest.superbet.event_finalize import maybe_finalize_finished_event
from ingest.superbet.benchmark import h2h_overround, market_benchmark
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.live_ticks import append_live_tick
from ingest.superbet.parser import SuperbetEventSnapshot
from ingest.superbet.store import save_event_snapshot
from config import settings
from models.wc_against_model import build_against_model_alerts
from models.wc_bet_advice import UserBetInput, build_bet_advice_report
from models.wc_bet_strategy import build_bet_strategy_report
from models.wc_hedge_advisor import advise_open_bets, hedge_report_to_dict
from models.wc_inplay import inplay_from_predictor
from models.wc_trend_advisor import (
    analyze_position,
    load_event_ticks,
    trend_report_to_dict,
)
from schemas.national_teams import normalize_national_team

logger = logging.getLogger(__name__)

_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}


def _build_hedge_report(
    inplay_dict: dict[str, Any],
    snapshot: SuperbetEventSnapshot,
    minute: int,
    home_team: str,
    away_team: str,
) -> dict[str, Any] | None:
    """Constrói o hedge report se houver apostas abertas do usuário."""
    try:
        from api.user_bets_store import get_bets_for_event

        user_bets = get_bets_for_event(home_team, away_team, status="open")
        if not user_bets:
            return None
        report = advise_open_bets(
            open_bets=user_bets,
            inplay=inplay_dict,
            snapshot=snapshot,
            minute=minute,
            home_team=home_team,
            away_team=away_team,
        )
        return hedge_report_to_dict(report)
    except Exception as exc:
        logger.warning("Erro ao construir hedge_report: %s", exc)
        return None


def _build_against_model_alerts(
    *,
    predictor: Any,
    inplay_dict: dict[str, Any],
    home_team: str,
    away_team: str,
    phase: str,
    user_bet: UserBetInput | None,
) -> list[dict[str, Any]]:
    """Alertas vermelhos quando apostas 1X2 divergem do palpite pré-jogo / ao vivo."""
    try:
        from api.user_bets_store import get_bets_for_event

        pre = predictor.predict(home_team, away_team, phase=phase)
        pregame_probs = {"1": pre.prob_home, "X": pre.prob_draw, "2": pre.prob_away}
        open_bets = get_bets_for_event(home_team, away_team, status="open")
        user_bet_dict = None
        if user_bet is not None:
            user_bet_dict = {
                "market": user_bet.market,
                "outcome": user_bet.outcome,
                "stake": user_bet.stake,
                "odds_placed": user_bet.odds_placed,
            }
        return build_against_model_alerts(
            open_bets=open_bets,
            inplay=inplay_dict,
            pregame_prediction=pre.prediction,
            pregame_probs=pregame_probs,
            home_team=home_team,
            away_team=away_team,
            phase=phase,
            user_bet=user_bet_dict,
        )
    except Exception as exc:
        logger.warning("Erro ao construir against_model_alerts: %s", exc)
        return []


def _build_trend_report(
    event_id: int,
    home_team: str,
    away_team: str,
    event_snapshot_raw: dict[str, Any],
) -> dict[str, Any] | None:
    """Analisa tendência do jogo e conselho de posição (copiloto).

    Lê ticks anteriores do evento e cruza com apostas abertas do usuário.
    """
    try:
        from api.user_bets_store import get_bets_for_event
        from config import settings
        event_dir = Path(settings.lake_root) / "bronze" / "superbet" / "events" / str(event_id)
        ticks = load_event_ticks(event_dir)
        if len(ticks) < 2:
            return None

        # Pegar aposta do usuário para o evento (se existir)
        user_bets = get_bets_for_event(home_team, away_team, status="open")
        if not user_bets:
            # Sem aposta aberta → análise de tendência pura (sem conselho de posição)
            # Usar bet fictícia para pelo menos retornar sinais/oportunidades
            user_bet = {"picks": []}
        else:
            user_bet = user_bets[0]  # Primeira aposta relevante

        report = analyze_position(user_bet, ticks, event_snapshot_raw)
        return trend_report_to_dict(report)
    except Exception as exc:
        logger.warning("Erro ao construir trend_report: %s", exc)
        return None


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

    # --- Momentum: escanteios + eventos Sofascore ao vivo ---
    momentum_events: list[dict] = []
    sofascore_event_id: int | None = None
    live_stats: dict[str, float | None] = {}
    if snapshot.inplay and settings.inplay_use_sofascore_live:
        try:
            from datetime import UTC, datetime

            from ingest.sofascore.live_momentum import enrich_momentum_from_sofascore
            from ingest.sofascore.live_stats import fetch_live_match_stats

            ss_events, sofascore_event_id = enrich_momentum_from_sofascore(
                home,
                away,
                match_date=datetime.now(UTC).date(),
                save_bronze=True,
            )
            momentum_events.extend(ss_events)
            if sofascore_event_id:
                live_stats = fetch_live_match_stats(sofascore_event_id)
        except Exception as exc:
            logger.warning("sofascore_momentum_falha event_id=%s: %s", event_id, exc)

    if snapshot.inplay:
        ip = snapshot.inplay
        for _ in range(ip.home_corners):
            momentum_events.append({
                "event_type": "corner",
                "minute": minute,
                "team": "home",
                "detail": "escanteio",
                "source": "superbet",
            })
        for _ in range(ip.away_corners):
            momentum_events.append({
                "event_type": "corner",
                "minute": minute,
                "team": "away",
                "detail": "escanteio",
                "source": "superbet",
            })

    ip_stats = snapshot.inplay
    tick_extra = {
        "home_corners": ip_stats.home_corners if ip_stats else 0,
        "away_corners": ip_stats.away_corners if ip_stats else 0,
        "home_red_cards": sum(
            1 for e in momentum_events if e.get("event_type") == "red_card" and e.get("team") == "home"
        ),
        "away_red_cards": sum(
            1 for e in momentum_events if e.get("event_type") == "red_card" and e.get("team") == "away"
        ),
        "n_sofascore_events": sum(1 for e in momentum_events if e.get("source") == "sofascore"),
        "home_xg": live_stats.get("home_xg"),
        "away_xg": live_stats.get("away_xg"),
        "home_possession_pct": live_stats.get("home_possession_pct"),
        "away_possession_pct": live_stats.get("away_possession_pct"),
    }

    from models.wc_market_shrinkage import market_probs_from_h2h_implied

    market_probs = market_probs_from_h2h_implied(snapshot.h2h_implied)

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
        momentum_events=momentum_events,
        home_corners=ip.home_corners if snapshot.inplay else 0,
        away_corners=ip.away_corners if snapshot.inplay else 0,
        market_probs=market_probs,
    )
    inplay_dict = result.to_dict()
    shadow = inplay_dict.get("ensemble_shadow") or {}
    tick_extra["ens_prob_final_home"] = shadow.get("prob_final_home")
    tick_extra["ens_prob_l1_delta"] = shadow.get("prob_l1_delta")
    report = build_bet_advice_report(
        home_team=home,
        away_team=away,
        inplay=inplay_dict,
        snapshot=snapshot,
        user_bet=user_bet,
        minute=minute,
        bankroll=bankroll,
        features=result.features,
    )

    snapshot_dict = snapshot.to_dict()
    if save_tick:
        try:
            append_live_tick(
                event_id=event_id,
                snapshot=snapshot_dict,
                inplay=inplay_dict,
                advice=report,
                tick_extra=tick_extra,
            )
        except Exception as exc:
            logger.warning("Falha ao gravar live_ticks parquet (event_id=%s): %s", event_id, exc)

    is_finished = str(status or "").upper() in _FINISHED_STATUSES

    finalize_info = maybe_finalize_finished_event(
        event_id=event_id,
        snapshot=snapshot,
        inplay=inplay_dict,
        advice=report,
        is_finished=is_finished,
    )

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

    pre = predictor.predict(home, away, phase=phase)
    pregame_probs = {"1": pre.prob_home, "X": pre.prob_draw, "2": pre.prob_away}
    inplay_probs = {
        "1": float(inplay_dict.get("prob_final_home") or 0),
        "X": float(inplay_dict.get("prob_final_draw") or 0),
        "2": float(inplay_dict.get("prob_final_away") or 0),
    }
    from models.bet_guardrails import build_bet_guardrails_payload

    bet_guardrails = build_bet_guardrails_payload(
        minute=minute,
        pregame_prediction=pre.prediction,
        pregame_probs=pregame_probs,
        inplay_probs=inplay_probs,
    )
    aportes_out = report.get("aportes", [])
    if minute >= settings.live_block_minute:
        aportes_out = []

    return {
        "home_team": home,
        "away_team": away,
        "minute": minute,
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label,
        "status": status,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
        "sofascore_event_id": sofascore_event_id,
        "n_momentum_events": len(momentum_events),
        "event_finalize": finalize_info,
        "cashout": report.get("cashout"),
        "aportes": aportes_out,
        "inplay_summary": {
            "prob_final_home": inplay_dict.get("prob_final_home"),
            "prob_final_draw": inplay_dict.get("prob_final_draw"),
            "prob_final_away": inplay_dict.get("prob_final_away"),
            "prob_ht_home": inplay_dict.get("prob_ht_home"),
            "prob_ht_draw": inplay_dict.get("prob_ht_draw"),
            "prob_ht_away": inplay_dict.get("prob_ht_away"),
            "prob_sh_home": inplay_dict.get("prob_sh_home"),
            "prob_sh_draw": inplay_dict.get("prob_sh_draw"),
            "prob_sh_away": inplay_dict.get("prob_sh_away"),
            "over_2_5": inplay_dict.get("final_line_probs", {}).get("over_2_5"),
            "btts": inplay_dict.get("btts_final"),
            "prob_next_goal_home": inplay_dict.get("prob_next_goal_home"),
            "prob_next_goal_away": inplay_dict.get("prob_next_goal_away"),
            "prob_no_more_goals": inplay_dict.get("prob_no_more_goals"),
            "ht_correct_scores": inplay_dict.get("ht_correct_scores"),
            "sh_correct_scores": inplay_dict.get("sh_correct_scores"),
            "ht_exact_totals": inplay_dict.get("ht_exact_totals"),
            "sh_exact_totals": inplay_dict.get("sh_exact_totals"),
            "ht_line_probs": inplay_dict.get("ht_line_probs"),
            "second_half_line_probs": inplay_dict.get("second_half_line_probs"),
            "ht_handicap_probs": inplay_dict.get("ht_handicap_probs"),
            "sh_handicap_probs": inplay_dict.get("sh_handicap_probs"),
        },
        "half_markets": snapshot.half_markets,
        "first_half_totals": snapshot.first_half_totals,
        "second_half_totals": snapshot.second_half_totals,
        "superbet_event_id": event_id,
        "h2h_odds": snapshot.h2h_odds,
        "h2h_implied": snapshot.h2h_implied,
        "h2h_overround": overround,
        "generosity_probs": snapshot.generosity_probs,
        "confidence": report.get("confidence"),
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
            confidence=report.get("confidence"),
            event_id=event_id,
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
            "first_half": bool(snapshot.half_markets.get("1h") or snapshot.first_half_totals),
            "second_half": bool(snapshot.half_markets.get("2h") or snapshot.second_half_totals),
        },
        "hedge_report": _build_hedge_report(
            inplay_dict=inplay_dict,
            snapshot=snapshot,
            minute=minute,
            home_team=home,
            away_team=away,
        ),
        "against_model_alerts": _build_against_model_alerts(
            predictor=predictor,
            inplay_dict=inplay_dict,
            home_team=home,
            away_team=away,
            phase=phase,
            user_bet=user_bet,
        ),
        "bet_guardrails": bet_guardrails,
        "trend_report": _build_trend_report(
            event_id=event_id,
            home_team=home,
            away_team=away,
            event_snapshot_raw=snapshot_dict,
        ),
    }


__all__ = ["SuperbetClientError", "run_live_advice"]
