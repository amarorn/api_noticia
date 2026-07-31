"""Orquestra Superbet ao vivo → modelo in-play → cash-out / aportes."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ingest.superbet.event_finalize import maybe_finalize_finished_event
from ingest.superbet.benchmark import h2h_overround, market_benchmark
from ingest.superbet.client import SuperbetClient, SuperbetClientError
from ingest.superbet.live_ticks import append_live_tick
from ingest.superbet.live_stats_payload import build_live_stats_payload
from ingest.superbet.live_advice_cache import advice_cache_key, get_stale_advice_for_event, run_with_advice_cache
from ingest.superbet.parser import SuperbetEventSnapshot
from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
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
from ingest.superbet.team_resolver import classify_live_match, resolve_club_competition
from models.wc_combo_optimizer import build_optimized_tickets, tickets_to_dict

logger = logging.getLogger(__name__)

_FINISHED_STATUSES = {"FINISHED", "ENDED", "CLOSED", "CANCELLED", "ABANDONED"}
_FINISHED_LABEL_HINTS = ("END", "FIM", "ENCERR", "FINAL", "FT", "TERMIN")


def _match_is_finished(
    *,
    status: str | None,
    period_label: str | None,
    minute: int,
    match_minutes: int = 90,
    is_live_snapshot: bool = True,
    home_score: int = 0,
    away_score: int = 0,
) -> bool:
    st = str(status or "").upper()
    if st in _FINISHED_STATUSES:
        return True
    lbl = str(period_label or "").upper()
    if lbl and any(h in lbl for h in _FINISHED_LABEL_HINTS):
        return True
    if minute >= match_minutes + 15:
        return True
    # Saiu do feed ao vivo mas bronze ainda tem stats de fim de jogo
    if (
        not is_live_snapshot
        and minute >= max(85, match_minutes - 5)
        and (home_score + away_score > 0 or minute > 50)
    ):
        return True
    return False


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
    before_date: Any | None = None,
) -> list[dict[str, Any]]:
    """Alertas vermelhos quando apostas 1X2 divergem do palpite pré-jogo / ao vivo."""
    try:
        from api.user_bets_store import get_bets_for_event

        pre = predictor.predict(home_team, away_team, phase=phase, before_date=before_date)
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
    phase: str = "league",
    bankroll: float = 1000.0,
    user_bet: UserBetInput | None = None,
    save_bronze: bool = True,
    save_tick: bool = True,
    use_sofascore_live: bool | None = None,
    client: SuperbetClient | None = None,
    fast: bool = False,
    kickoff: str | None = None,
) -> dict[str, Any]:
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
        from ingest.superbet.live_pulse_registry import record_from_advice_payload

        record_from_advice_payload(cached, superbet_stale=True)
        return cached

    if save_bronze and not superbet_stale:
        save_event_snapshot(snapshot)

    home, away, match_kind = classify_live_match(snapshot.home_team, snapshot.away_team)

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

    cache_key = advice_cache_key(
        event_id=event_id,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        bankroll=bankroll,
        fast=fast,
            phase=phase,
            match_kind=match_kind,
        )

    def _compute() -> dict[str, Any]:
        return _build_live_advice_payload(
            event_id=event_id,
            predictor=predictor,
            snapshot=snapshot,
            home=home,
            away=away,
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            ht_h=ht_h,
            ht_a=ht_a,
            status=status,
            period_label=period_label,
            phase=phase,
            bankroll=bankroll,
            user_bet=user_bet,
            save_tick=save_tick,
            use_sofascore_live=use_sofascore_live,
            fast=fast,
            kickoff=kickoff,
            match_kind=match_kind,
        )

    payload = run_with_advice_cache(cache_key, _compute, fast=fast)
    if superbet_stale:
        payload = dict(payload)
        payload["superbet_stale"] = True
    from ingest.superbet.live_pulse_registry import record_from_advice_payload

    record_from_advice_payload(payload, superbet_stale=superbet_stale)
    return payload


def _build_live_advice_payload(
    *,
    event_id: int,
    predictor: Any,
    snapshot: SuperbetEventSnapshot,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    minute: int,
    ht_h: int | None,
    ht_a: int | None,
    status: str | None,
    period_label: str | None,
    phase: str,
    bankroll: float,
    user_bet: UserBetInput | None,
    save_tick: bool,
    use_sofascore_live: bool | None,
    fast: bool,
    kickoff: str | None = None,
    match_kind: str = "national",
) -> dict[str, Any]:
    from pipelines.wc_predict_utils import resolve_inplay_before_date
    from pipelines.wc_schedule import find_schedule_match

    schedule_match = find_schedule_match(home, away)
    effective_phase = phase
    if match_kind == "club" and phase in {"friendly", "group", "league"}:
        effective_phase = "league"
    elif schedule_match and phase == "friendly":
        effective_phase = schedule_match.get("phase") or phase

    model_before_date = resolve_inplay_before_date(
        home,
        away,
        kickoff_iso=kickoff or (schedule_match or {}).get("kickoff"),
        snapshot_utc_date=snapshot.utc_date,
    )
    # --- Momentum: escanteios + eventos Sofascore ao vivo ---
    momentum_events: list[dict] = []
    sofascore_event_id: int | None = None
    live_stats: dict[str, float | None] = {}
    sofascore_skipped: str | None = None
    sofascore_live = (
        settings.inplay_use_sofascore_live if use_sofascore_live is None else use_sofascore_live
    )
    if snapshot.inplay and sofascore_live and not fast:
        from ingest.sofascore.client import SofascoreClient

        if SofascoreClient.is_globally_blocked():
            remaining = int(SofascoreClient.waf_cooldown_remaining_sec())
            sofascore_skipped = (
                f"Sofascore em cooldown ({remaining}s) — usando dados Superbet e estimativa de posse."
            )
            logger.info("sofascore_skip_cooldown event_id=%s remaining_sec=%s", event_id, remaining)
        else:
            try:

                from ingest.sofascore.live_momentum import enrich_momentum_from_sofascore
                from ingest.sofascore.live_stats import fetch_live_match_stats

                ss_events, sofascore_event_id = enrich_momentum_from_sofascore(
                    home,
                    away,
                    match_date=model_before_date.date(),
                    save_bronze=True,
                    waf_max_retries=settings.inplay_sofascore_waf_max_retries,
                )
                momentum_events.extend(ss_events)
                if sofascore_event_id:
                    live_stats = fetch_live_match_stats(
                        sofascore_event_id,
                        waf_max_retries=settings.inplay_sofascore_waf_max_retries,
                    )
            except Exception as exc:
                logger.warning("sofascore_momentum_falha event_id=%s: %s", event_id, exc)
                sofascore_skipped = "Sofascore indisponível — posse estimada por escanteios."

    scorealarm_context: dict | None = None
    if snapshot.inplay and settings.scorealarm_enabled and not fast:
        try:
            from ingest.superbet.scorealarm.service import (
                fetch_scorealarm_context,
                scorealarm_to_live_stats,
            )

            scorealarm_context = fetch_scorealarm_context(
                event_id,
                home_team=home,
                away_team=away,
            )
            if scorealarm_context:
                sa_live = scorealarm_to_live_stats(scorealarm_context)
                for key, value in sa_live.items():
                    if value is not None and live_stats.get(key) is None:
                        live_stats[key] = value
                from models.wc_inplay_live_adjust import scorealarm_timeline_to_momentum_events

                momentum_events.extend(
                    scorealarm_timeline_to_momentum_events(scorealarm_context.get("timeline"))
                )
        except Exception as exc:
            logger.warning("scorealarm_context_falha event_id=%s: %s", event_id, exc)

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

    # --- Live Research Pulse: deep research em eventos críticos ---
    live_research_result: dict[str, Any] | None = None
    logger.warning("live_research_check event_id=%s inplay=%s gemini=%s fast=%s minute=%s", 
                event_id, snapshot.inplay is not None, bool(settings.gemini_api_key), fast, minute)
    if snapshot.inplay and settings.gemini_api_key and not fast and minute >= 15:
        try:
            from ingest.research.live_research_pulse import live_research_pulse

            live_research_result = live_research_pulse(
                event_id=str(event_id),
                home_team=home,
                away_team=away,
                minute=minute,
                home_score=home_score,
                away_score=away_score,
                recent_events=momentum_events,
            )
            logger.warning("live_research_result event_id=%s result=%s", event_id, live_research_result is not None)
        except Exception as exc:
            logger.warning("live_research_pulse_falha event_id=%s: %s", event_id, exc)
    else:
        logger.info("live_research_skipped event_id=%s reason=conditions_not_met", event_id)

    from models.wc_market_shrinkage import market_probs_from_h2h_implied
    from ingest.superbet.halftime_snapshot import load_or_freeze_halftime
    from models.wc_halftime_adjust import build_halftime_report

    market_probs = market_probs_from_h2h_implied(snapshot.h2h_implied)

    # Contexto de análise pré-jogo enviado pelo usuário (árbitro, xG, H2H…)
    from ingest.superbet.match_context_store import load_match_context, load_match_context_by_teams
    from models.wc_referee_inplay import (
        parse_referee_from_match_context,
        referee_card_market_probs,
    )

    match_context = load_match_context(event_id)
    # Fallback: usa contexto salvo via análise pré-jogo (por nome dos times)
    if match_context is None:
        match_context = load_match_context_by_teams(home, away)
    referee_card_lambda: float | None = (match_context or {}).get("referee_card_lambda")
    referee_profile = parse_referee_from_match_context(match_context)

    halftime_stats = load_or_freeze_halftime(event_id, snapshot) if snapshot.inplay else None

    inplay_live_stats = (
        {k: float(v) for k, v in live_stats.items() if v is not None}
        if live_stats
        else None
    )
    inplay_live_timeline = (
        (scorealarm_context or {}).get("timeline") if scorealarm_context else None
    )

    ip = snapshot.inplay
    sim_common = dict(
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        ht_home_score=ht_h,
        ht_away_score=ht_a,
        match_minutes=90,
        momentum_events=momentum_events,
        home_corners=ip.home_corners if snapshot.inplay else 0,
        away_corners=ip.away_corners if snapshot.inplay else 0,
        market_probs=market_probs,
        halftime_stats=halftime_stats,
        live_stats=inplay_live_stats,
        live_timeline=inplay_live_timeline,
        match_context=match_context,
        live_research=live_research_result,
    )

    if match_kind == "club":
        from models.league_inplay import inplay_for_club_match, inplay_for_market_prior_match

        club_competition = resolve_club_competition(home, away)
        if club_competition:
            result = inplay_for_club_match(
                competition=club_competition,
                before_date=model_before_date,
                n_simulations=settings.inplay_fast_mc_simulations if fast else None,
                **sim_common,
            )
            league_model_source = "league_dixon_coles"
        else:
            result = inplay_for_market_prior_match(
                before_date=model_before_date,
                n_simulations=settings.inplay_fast_mc_simulations if fast else None,
                **sim_common,
            )
            league_model_source = "market_prior"
    elif match_kind == "other":
        from models.league_inplay import inplay_for_market_prior_match

        result = inplay_for_market_prior_match(
            before_date=model_before_date,
            n_simulations=settings.inplay_fast_mc_simulations if fast else None,
            **sim_common,
        )
        league_model_source = "market_prior"
    else:
        league_model_source = "wc_ensemble"
        result = inplay_from_predictor(
            predictor,
            phase=effective_phase,
            is_neutral=True,
            before_date=model_before_date,
            n_simulations=settings.inplay_fast_mc_simulations if fast else None,
            use_ensemble=False if fast else None,
            **sim_common,
        )
    inplay_dict = result.to_dict()
    from models.wc_derived_markets import enrich_inplay_derived_probs

    inplay_dict.update(enrich_inplay_derived_probs(inplay_dict))
    inplay_dict["ht_home_score"] = ht_h
    inplay_dict["ht_away_score"] = ht_a
    inplay_dict["model_before_date"] = model_before_date.isoformat()
    # Adiciona alertas do live research (deep research ao vivo)
    if live_research_result:
        inplay_dict["live_research"] = {
            "eventos_detectados": live_research_result.get("eventos_detectados", []),
            "alertas_ao_vivo": live_research_result.get("alertas_ao_vivo", []),
            "recomendacao_modelo": live_research_result.get("recomendacao_modelo", "manter"),
            "confianca_alteracao": live_research_result.get("confianca_alteracao", "Baixa"),
            "justificativa": live_research_result.get("justificativa", ""),
            "_cached": live_research_result.get("_cached", False),
        }
    try:
        if match_kind == "club":
            from models.league_inplay import league_pregame_probs

            club_competition = resolve_club_competition(home, away)
            pre_probs = (
                league_pregame_probs(
                    home,
                    away,
                    competition=club_competition,
                    before_date=model_before_date,
                )
                if club_competition
                else None
            )
            if pre_probs:
                inplay_dict["pregame_probs"] = {k: round(pre_probs[k], 4) for k in ("1", "X", "2")}
            else:
                raise ValueError("sem fixtures de liga")
        elif match_kind == "other":
            raise ValueError("ligas estrangeiras usam prior de mercado")
        else:
            pre = predictor.predict(
                home,
                away,
                phase=effective_phase,
                is_neutral=True,
                before_date=model_before_date,
            )
            inplay_dict["pregame_probs"] = {
                "1": round(pre.prob_home, 4),
                "X": round(pre.prob_draw, 4),
                "2": round(pre.prob_away, 4),
            }
    except Exception:
        inplay_dict["pregame_probs"] = {
            "1": market_probs[0] if market_probs else None,
            "X": market_probs[1] if market_probs else None,
            "2": market_probs[2] if market_probs else None,
        }

    # --- Mercados de árbitro (cartões, faltas, pênaltis) ---
    referee_markets = None
    if referee_profile:
        try:
            current_yellow = 0
            if snapshot.inplay:
                current_yellow = (snapshot.inplay.home_yellow_cards or 0) + (snapshot.inplay.away_yellow_cards or 0)
            referee_markets = referee_card_market_probs(
                referee=referee_profile,
                minute=minute,
                match_minutes=90,
                current_yellow_cards=current_yellow,
            )
            inplay_dict["referee_markets"] = referee_markets
            inplay_dict["referee_profile"] = referee_profile.to_dict()
        except Exception as exc:
            logger.warning("referee_markets_error event_id=%s: %s", event_id, exc)

    if fast:
        ht_report = None
    else:
        corner_lambda_home: float | None = None
        corner_lambda_away: float | None = None
        try:
            from models.corners_predictor import CornersPredictor

            cp = CornersPredictor(fixtures_df=predictor.fixtures)
            corner_pred = cp.predict(home, away, phase=effective_phase)
            corner_lambda_home = corner_pred.factors.lambda_home
            corner_lambda_away = corner_pred.factors.lambda_away
        except Exception:
            pass

        corner_lines = (
            tuple(float(k) for k in snapshot.corners.keys()) if snapshot.corners else None
        )

        if halftime_stats is not None:
            halftime_report_obj = build_halftime_report(
                halftime_stats,
                lambda_full_home=result.lambda_full_home,
                lambda_full_away=result.lambda_full_away,
                corner_lambda_home=corner_lambda_home,
                corner_lambda_away=corner_lambda_away,
                corner_lines=corner_lines,
                card_lines=tuple(float(k) for k in snapshot.yellow_cards.keys())
                if snapshot.yellow_cards
                else None,
                referee_card_lambda=referee_card_lambda,
            )
            if halftime_report_obj is not None:
                ht_report = halftime_report_obj.to_dict()
                inplay_dict["corner_line_probs"] = ht_report.get("corner_line_probs") or {}
                inplay_dict["card_line_probs"] = ht_report.get("card_line_probs") or {}
            else:
                ht_report = None
        elif corner_lambda_home is not None and corner_lambda_away is not None:
            from models.wc_halftime_adjust import project_live_corners, project_pregame_corners

            live_corner_lines = corner_lines or (7.5, 8.5, 9.5, 10.5, 11.5)
            if snapshot.inplay:
                corners_proj = project_live_corners(
                    home_corners=int(snapshot.inplay.home_corners),
                    away_corners=int(snapshot.inplay.away_corners),
                    minute=minute,
                    lambda_home_ft=corner_lambda_home,
                    lambda_away_ft=corner_lambda_away,
                    lines=live_corner_lines,
                )
            else:
                corners_proj = project_pregame_corners(
                    lambda_home_ft=corner_lambda_home,
                    lambda_away_ft=corner_lambda_away,
                    lines=live_corner_lines,
                )
            inplay_dict["corners_projection"] = corners_proj
            inplay_dict["corner_line_probs"] = corners_proj.get("line_probs") or {}
            from models.wc_derived_markets import corners_h2h_probs, team_corner_line_probs

            ch2h = corners_h2h_probs(inplay_dict)
            if ch2h:
                inplay_dict["corners_h2h_probs"] = ch2h
            home_corner_lines = tuple(
                float(k) for k in (snapshot.team_corners or {}).get("home", {})
            )
            away_corner_lines = tuple(
                float(k) for k in (snapshot.team_corners or {}).get("away", {})
            )
            if home_corner_lines or away_corner_lines:
                obs_h = int(snapshot.inplay.home_corners) if snapshot.inplay else 0
                obs_a = int(snapshot.inplay.away_corners) if snapshot.inplay else 0
                inplay_dict["team_corner_line_probs"] = team_corner_line_probs(
                    lambda_home_ft=float(corners_proj.get("expected_ft_home") or corner_lambda_home),
                    lambda_away_ft=float(corners_proj.get("expected_ft_away") or corner_lambda_away),
                    observed_home=obs_h,
                    observed_away=obs_a,
                    home_lines=home_corner_lines,
                    away_lines=away_corner_lines,
                )
            ht_report = None
        else:
            ht_report = None

        if not inplay_dict.get("card_line_probs"):
            card_lines = (
                tuple(float(k) for k in snapshot.yellow_cards.keys())
                if snapshot.yellow_cards
                else (2.5, 3.5, 4.5, 5.5)
            )
            card_lambda = referee_card_lambda if referee_card_lambda is not None else 3.8
            if snapshot.yellow_cards or referee_card_lambda is not None:
                from models.wc_halftime_adjust import project_pregame_cards

                if snapshot.inplay and minute > 0:
                    from models.wc_halftime_adjust import _over_under_probs_from_total

                    observed = int(snapshot.inplay.home_yellow_cards) + int(
                        snapshot.inplay.away_yellow_cards
                    )
                    remaining_lam = max(0.5, card_lambda - observed * 0.5)
                    ft_lam = observed + remaining_lam
                    cards_proj = {
                        "source": "live_poisson",
                        "expected_ft_total": round(ft_lam, 3),
                        "line_probs": _over_under_probs_from_total(ft_lam, observed, card_lines),
                    }
                else:
                    cards_proj = project_pregame_cards(
                        referee_card_lambda=card_lambda,
                        lines=card_lines,
                    )
                inplay_dict["card_line_probs"] = cards_proj.get("line_probs") or {}
                inplay_dict["cards_projection"] = cards_proj

        from models.wc_derived_markets import foul_line_probs, referee_foul_lambda_from_context

        foul_lam = referee_foul_lambda_from_context(match_context)
        if foul_lam is not None and (snapshot.fouls or match_context):
            foul_lines = (
                tuple(float(k) for k in snapshot.fouls.keys())
                if snapshot.fouls
                else (20.5, 25.5, 30.5)
            )
            inplay_dict["foul_line_probs"] = foul_line_probs(foul_lam, foul_lines)

    if fast and not inplay_dict.get("foul_line_probs"):
        from models.wc_derived_markets import foul_line_probs, referee_foul_lambda_from_context

        foul_lam = referee_foul_lambda_from_context(match_context)
        if foul_lam is not None and (snapshot.fouls or match_context):
            foul_lines = (
                tuple(float(k) for k in snapshot.fouls.keys())
                if snapshot.fouls
                else (20.5, 25.5, 30.5)
            )
            inplay_dict["foul_line_probs"] = foul_line_probs(foul_lam, foul_lines)
    shadow = inplay_dict.get("ensemble_shadow") or {}
    tick_extra["ens_prob_final_home"] = shadow.get("prob_final_home")
    tick_extra["ens_prob_l1_delta"] = shadow.get("prob_l1_delta")
    snapshot_dict = snapshot.to_dict()
    trend_report = None
    if not fast:
        trend_report = _build_trend_report(
            event_id=event_id,
            home_team=home,
            away_team=away,
            event_snapshot_raw=snapshot_dict,
        )
    report = build_bet_advice_report(
        home_team=home,
        away_team=away,
        inplay=inplay_dict,
        snapshot=snapshot,
        user_bet=user_bet,
        minute=minute,
        bankroll=bankroll,
        features=result.features,
        trend_report=trend_report,
    )
    if scorealarm_context and scorealarm_context.get("prematch"):
        from ingest.superbet.scorealarm.prematch import apply_prematch_confidence_boost

        boosted = apply_prematch_confidence_boost(
            report.get("confidence"),
            scorealarm_context.get("prematch"),
        )
        if boosted is not None:
            report["confidence"] = boosted

    if save_tick:
        try:
            append_live_tick(
                event_id=event_id,
                snapshot=snapshot_dict,
                inplay=inplay_dict,
                advice=report,
                tick_extra={**(tick_extra or {}), "match_kind": match_kind},
            )
        except Exception as exc:
            logger.warning("Falha ao gravar live_ticks parquet (event_id=%s): %s", event_id, exc)

    is_finished = _match_is_finished(
        status=status,
        period_label=period_label,
        minute=minute,
        match_minutes=int(inplay_dict.get("match_minutes") or 90),
        is_live_snapshot=snapshot.is_live,
        home_score=home_score,
        away_score=away_score,
    )

    finalize_info = None
    if not fast:
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

    inplay_probs = {
        "1": float(inplay_dict.get("prob_final_home") or 0),
        "X": float(inplay_dict.get("prob_final_draw") or 0),
        "2": float(inplay_dict.get("prob_final_away") or 0),
    }
    if fast:
        from models.wc_draw_model import resolve_wc_outcome

        pregame_prediction = resolve_wc_outcome(inplay_probs, phase=effective_phase)
        pregame_probs = inplay_probs
    else:
        pre = predictor.predict(
            home,
            away,
            phase=effective_phase,
            is_neutral=True,
            before_date=model_before_date,
        )
        pregame_probs = {"1": pre.prob_home, "X": pre.prob_draw, "2": pre.prob_away}
        pregame_prediction = pre.prediction
    from models.bet_guardrails import build_bet_guardrails_payload

    aportes_out = report.get("aportes", [])

    strategy_report = build_bet_strategy_report(
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
        fast=fast,
    )

    bet_guardrails = build_bet_guardrails_payload(
        minute=minute,
        pregame_prediction=pregame_prediction,
        pregame_probs=pregame_probs,
        inplay_probs=inplay_probs,
        home_score=home_score,
        away_score=away_score,
        ht_home=ht_h,
        ht_away=ht_a,
        market_scan=strategy_report.get("market_scan") or [],
    )

    half_tickets = None
    from models.wc_inplay_half_tickets import build_inplay_half_tickets

    half_tickets = build_inplay_half_tickets(
        strategy_report.get("market_scan") or [],
        minute=minute,
        bankroll=bankroll,
    )

    from models.wc_viable_2h_markets import build_viable_2h_markets
    from models.super_multipla_suggestions import build_super_multipla_block

    viable_2h_markets = build_viable_2h_markets(
        strategy_report.get("market_scan") or [],
        minute=minute,
        match_minutes=inplay_dict.get("match_minutes") or 90,
        remaining_fraction=inplay_dict.get("remaining_fraction"),
    )

    from ingest.superbet.score_stale import detect_score_stale, load_last_live_tick

    score_stale_report = detect_score_stale(
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        scorealarm_timeline=(scorealarm_context or {}).get("timeline") if scorealarm_context else None,
        last_tick=load_last_live_tick(event_id) if not fast else None,
    )

    return {
        "home_team": home,
        "away_team": away,
        "match_kind": match_kind,
        "model_source": league_model_source if match_kind in {"club", "other"} else "wc_ensemble",
        "minute": minute,
        "current_score": inplay_dict.get("current_score"),
        "period_label": period_label,
        "status": status,
        "is_finished": is_finished,
        "is_live": snapshot.is_live and not is_finished,
        "score_stale": score_stale_report,
        "sofascore_event_id": sofascore_event_id,
        "n_momentum_events": len(momentum_events),
        "event_finalize": finalize_info,
        "match_context": match_context,
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
            "top_final_scores": inplay_dict.get("top_final_scores"),
            "ht_correct_scores": inplay_dict.get("ht_correct_scores"),
            "sh_correct_scores": inplay_dict.get("sh_correct_scores"),
            "ht_exact_totals": inplay_dict.get("ht_exact_totals"),
            "sh_exact_totals": inplay_dict.get("sh_exact_totals"),
            "ht_line_probs": inplay_dict.get("ht_line_probs"),
            "second_half_line_probs": inplay_dict.get("second_half_line_probs"),
            "ht_handicap_probs": inplay_dict.get("ht_handicap_probs"),
            "sh_handicap_probs": inplay_dict.get("sh_handicap_probs"),
            "ft_handicap_probs": inplay_dict.get("ft_handicap_probs"),
            "ft_asian_handicap_probs": inplay_dict.get("ft_asian_handicap_probs"),
            "corner_line_probs": inplay_dict.get("corner_line_probs"),
            "card_line_probs": inplay_dict.get("card_line_probs"),
            "referee_markets": inplay_dict.get("referee_markets"),
            "referee_profile": inplay_dict.get("referee_profile"),
            "halftime_adjustment": inplay_dict.get("halftime_adjustment"),
            "model_before_date": inplay_dict.get("model_before_date"),
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
        "strategy": strategy_report,
        "half_tickets": half_tickets,
        "viable_2h_markets": viable_2h_markets,
        "super_multipla": build_super_multipla_block(
            strategy_report.get("market_scan") or [],
            superbet_event_id=event_id,
            minute=minute,
            home_score=home_score,
            away_score=away_score,
            is_live=snapshot.is_live and not is_finished,
        )
        if not fast
        else None,
        "optimized_tickets": (
            tickets_to_dict(
                build_optimized_tickets(
                    strategy_report.get("market_scan") or [],
                    minute=minute,
                    home_score=home_score,
                    away_score=away_score,
                    ht_home=ht_h if snapshot.inplay else None,
                    ht_away=ht_a if snapshot.inplay else None,
                    bankroll=bankroll,
                    max_legs=4,
                    min_legs=2,
                    top_k=5,
                    min_ev=0.0,
                    min_combined_odd=1.5,
                    max_combined_odd=20.0,
                )
            )
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
            "halftime_adjust": bool(ht_report and ht_report.get("applied")),
            "corners": bool(snapshot.corners),
            "yellow_cards": bool(snapshot.yellow_cards),
        },
        "halftime_report": ht_report,
        "corners_projection": inplay_dict.get("corners_projection"),
        "hedge_report": None
        if fast
        else _build_hedge_report(
            inplay_dict=inplay_dict,
            snapshot=snapshot,
            minute=minute,
            home_team=home,
            away_team=away,
        ),
        "against_model_alerts": []
        if fast
        else _build_against_model_alerts(
            predictor=predictor,
            inplay_dict=inplay_dict,
            home_team=home,
            away_team=away,
            phase=effective_phase,
            user_bet=user_bet,
            before_date=model_before_date,
        ),
        "bet_guardrails": bet_guardrails,
        "trend_report": trend_report if not fast else None,
        "live_stats": build_live_stats_payload(
            snapshot=snapshot,
            live_stats=live_stats,
            tick_extra=tick_extra,
            sofascore_event_id=sofascore_event_id,
            sofascore_skipped=sofascore_skipped,
            prob_next_goal_home=float(inplay_dict.get("prob_next_goal_home") or 0),
            prob_next_goal_away=float(inplay_dict.get("prob_next_goal_away") or 0),
            scorealarm_stats=(scorealarm_context or {}).get("stats"),
            scorealarm_stale=bool((scorealarm_context or {}).get("stale")),
        ),
        "live_research": inplay_dict.get("live_research"),
        "live_kelly": _build_live_kelly_block(
            strategy_report=strategy_report,
            minute=minute,
            confidence_report=report.get("confidence"),
            bankroll=bankroll,
        ),
        "scorealarm": None
        if fast or not scorealarm_context
        else {
            "available": scorealarm_context.get("available"),
            "stale": scorealarm_context.get("stale"),
            "timeline": scorealarm_context.get("timeline") or [],
            "h2h": scorealarm_context.get("h2h"),
            "prematch": scorealarm_context.get("prematch"),
            "players": scorealarm_context.get("players") or [],
            "social": scorealarm_context.get("social"),
            "stats": scorealarm_context.get("stats") or {},
            "scores_id": scorealarm_context.get("scores_id"),
        },
    }


def _build_live_kelly_block(
    strategy_report: dict,
    minute: float,
    confidence_report: dict | None,
    bankroll: float = 1000.0,
) -> dict:
    """Adiciona Kelly dinâmico ao bloco de advice (Item 2: KXL dinâmico ao vivo)."""
    try:
        from models.wc_kelly_live import (
            compute_live_kxl_weight,
            enrich_opportunity_with_live_kelly,
        )

        confidence_score = float((confidence_report or {}).get("score") or 0.5)
        market_scan = list(strategy_report.get("market_scan") or [])
        n_events = len(market_scan)

        kxl_weight = compute_live_kxl_weight(
            minute=minute,
            confidence_score=confidence_score,
            n_live_events=n_events,
        )

        # Enriquecer os primeiros 5 aportes com Kelly dinâmico
        enriched = [
            enrich_opportunity_with_live_kelly(opp, minute, confidence_score, bankroll)
            for opp in market_scan[:5]
        ]

        return {
            "kxl_blend_dynamic": round(kxl_weight, 4),
            "minute": minute,
            "confidence_score": confidence_score,
            "top_enriched": enriched,
        }
    except Exception:
        return {}


__all__ = ["SuperbetClientError", "run_live_advice"]
