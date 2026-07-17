"""Orquestra Superbet ao vivo → modelo in-play de beisebol → advice."""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
from models.baseball_bet_advice import build_baseball_bet_advice_report
from models.baseball_inplay import simulate_baseball_inplay

logger = logging.getLogger(__name__)

_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}


def _match_is_finished(status: str | None, inning: int, match_innings: int = 9) -> bool:
    st = str(status or "").upper()
    if st in _FINISHED_STATUSES:
        return True
    if inning >= match_innings + 5:
        return True
    return False


def run_baseball_live_advice(
    event_id: int,
    *,
    bankroll: float = 1000.0,
    save_bronze: bool = True,
    fast: bool = False,
    client: SuperbetClient | None = None,
) -> dict[str, Any]:
    """Busca evento Superbet de beisebol e retorna advice in-play."""
    superbet_client = client or SuperbetClient()
    snapshot, superbet_stale = fetch_event_with_stale_fallback(superbet_client, event_id)

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
        # Para beisebol, minute armazena a entrada atual (ver parser).
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
    # Prior-only: linha inferida dos totais por time (não gera aportes — sem odd real)
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
        n_simulations=settings.baseball_fast_mc_simulations if fast else None,
    )
    inplay_dict = inplay_result.to_dict()

    report = build_baseball_bet_advice_report(
        inplay=inplay_result,
        snapshot=snapshot,
        bankroll=bankroll,
    )

    is_finished = _match_is_finished(
        status=status,
        inning=inning,
        match_innings=settings.baseball_match_innings,
    )

    return {
        "home_team": home_team,
        "away_team": away_team,
        "inning": inning,
        "minute": inning,  # compat com UI que espera minute
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label or f"{inning}I",
        "status": status,
        "baseball_innings": baseball_innings,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
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
            "rpi_home": inplay_dict["rpi_home"],
            "rpi_away": inplay_dict["rpi_away"],
            "rpi_home_prior": inplay_dict["rpi_home_prior"],
            "rpi_away_prior": inplay_dict["rpi_away_prior"],
            "match_innings": inplay_dict["match_innings"],
            "n_simulations": inplay_dict["n_simulations"],
            "market_total_line": inplay_dict["market_total_line"],
            "market_spread_line": inplay_dict["market_spread_line"],
        },
        "aportes": report["aportes"],
        "confidence": report["confidence"],
    }


__all__ = ["SuperbetClientError", "run_baseball_live_advice"]
