"""Orquestra Superbet ao vivo → modelo in-play de basquete → advice."""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.parser import SuperbetEventSnapshot
from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
from models.basket_bet_advice import build_basket_bet_advice_report
from models.basket_inplay import simulate_basket_inplay

logger = logging.getLogger(__name__)


_BASKET_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}


def _match_is_finished(status: str | None, minute: int, match_minutes: int = 48) -> bool:
    st = str(status or "").upper()
    if st in _BASKET_FINISHED_STATUSES:
        return True
    if minute >= match_minutes + 10:
        return True
    return False


def run_basket_live_advice(
    event_id: int,
    *,
    bankroll: float = 1000.0,
    save_bronze: bool = True,
    fast: bool = False,
    client: SuperbetClient | None = None,
) -> dict[str, Any]:
    """Busca evento Superbet de basquete e retorna advice in-play.

    O fluxo é análogo ao `run_live_advice` do futebol, mas usa o modelo dedicado de
    basquete (`models.basket_inplay`). Não depende do `WcPredictor`.
    """
    superbet_client = client or SuperbetClient()
    snapshot, superbet_stale = fetch_event_with_stale_fallback(superbet_client, event_id)

    if save_bronze and not superbet_stale:
        try:
            save_event_snapshot(snapshot)
        except Exception as exc:
            logger.warning("Falha ao salvar snapshot de basquete event_id=%s: %s", event_id, exc)

    # Validação branda de sport_id — não bloqueia, apenas alerta
    # TODO: confirmar sport_id real do basquete na Superbet BR
    sport_id = getattr(snapshot, "sport_id", None)
    if sport_id is not None and sport_id != settings.basket_sport_id:
        logger.info(
            "basket_advice_sport_id_inesperado event_id=%s sport_id=%s expected=%s",
            event_id,
            sport_id,
            settings.basket_sport_id,
        )

    home_team = snapshot.home_team
    away_team = snapshot.away_team

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score = ip.home_score
        away_score = ip.away_score
        minute = ip.minute
        status = ip.status
        period_label = ip.period_label
    else:
        home_score = away_score = minute = 0
        status = None
        period_label = None

    inplay_result = simulate_basket_inplay(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        match_minutes=settings.basket_match_minutes,
        moneyline_odds=snapshot.moneyline_odds,
        spread_odds=snapshot.spread_odds,
        total_points_odds=snapshot.total_points_odds,
        n_simulations=settings.basket_fast_mc_simulations if fast else None,
    )
    inplay_dict = inplay_result.to_dict()

    report = build_basket_bet_advice_report(
        inplay=inplay_result,
        snapshot=snapshot,
        bankroll=bankroll,
    )

    is_finished = _match_is_finished(
        status=status,
        minute=minute,
        match_minutes=settings.basket_match_minutes,
    )

    return {
        "home_team": home_team,
        "away_team": away_team,
        "minute": minute,
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label,
        "status": status,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
        "superbet_stale": superbet_stale,
        "superbet_event_id": event_id,
        "sport_id": sport_id,
        "captured_at": snapshot.captured_at,
        "h2h_odds": snapshot.moneyline_odds,
        "h2h_implied": snapshot.moneyline_implied,
        "spread_odds": snapshot.spread_odds,
        "spread_implied": snapshot.spread_implied,
        "total_points_odds": snapshot.total_points_odds,
        "total_points_implied": snapshot.total_points_implied,
        "inplay_summary": {
            "prob_home_win": inplay_dict.get("prob_home_win"),
            "prob_away_win": inplay_dict.get("prob_away_win"),
            "expected_final_home": inplay_dict.get("expected_final_home"),
            "expected_final_away": inplay_dict.get("expected_final_away"),
            "expected_total": inplay_dict.get("expected_total"),
            "remaining_minutes": inplay_dict.get("remaining_minutes"),
            "moneyline_probs": inplay_dict.get("moneyline_probs"),
            "spread_probs": inplay_dict.get("spread_probs"),
            "total_probs": inplay_dict.get("total_probs"),
            "ppm_home": inplay_dict.get("ppm_home"),
            "ppm_away": inplay_dict.get("ppm_away"),
            "market_total_line": inplay_dict.get("market_total_line"),
            "market_spread_line": inplay_dict.get("market_spread_line"),
        },
        "aportes": report.get("aportes", []),
        "confidence": report.get("confidence"),
    }


__all__ = ["run_basket_live_advice", "SuperbetClientError"]
