"""Rotas Copa do Mundo: previsões, round, schedule, squads, editions, validate, pregame."""

from __future__ import annotations

import asyncio
import json
import math
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

import api.deps as deps
from api.helpers import breakdown_to_response, sanitize_match_item, wc_prediction_to_response
from api.schemas import (
    WcCornerFactors,
    WcCornersPredictRequest,
    WcCornersPredictResponse,
    WcEditionItem,
    WcEditionMatchesResponse,
    WcEditionsResponse,
    WcFriendliesResponse,
    WcFriendlyItem,
    WcGroupStandingsBlock,
    WcGroupStandingsResponse,
    WcHistoricalMatchItem,
    WcPredictRequest,
    WcPredictionResponse,
    WcRoundResponse,
    WcScheduleResponse,
    WcSimulationResponse,
    WcSofascoreResolveResponse,
    WcSofascoreStatsResponse,
    WcSquadDetailResponse,
    WcSquadTeamItem,
    WcSquadTeamsResponse,
    WcTeamsResponse,
    WcValidateMatchInfo,
    WcValidateRequest,
    WcValidateResponse,
    WcValueRequest,
    WcValueResponse,
    SurebetOpportunityResponse,
    SurebetScanResponse,
    LiveCopilotAgentResponse,
    LiveCopilotResponse,
    PregameCopilotAgentRequest,
    PregameSummaryResponse,
)
from pipelines.wc_group_pressure import lookup_2026_group
from pipelines.wc_group_standings import (
    build_group_standings,
    build_group_standings_from_results,
    load_wc_group_results,
    merge_real_into_simulated,
)
from pipelines.wc_schedule import build_schedule_response, load_wc_schedule, official_match_exists
from pipelines.wc_squads import get_squad_by_team, list_squad_teams, load_wc_squads
from schemas.national_teams import normalize_national_team

WC_ROUND_FILE = Path("data/rounds/wc_2026.json")

router = APIRouter(prefix="/worldcup")


def _wc_round_cache():
    from api import wc_round_cache
    return wc_round_cache


def _load_wc_round(path: Path = WC_ROUND_FILE) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Rodada WC não encontrada: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler rodada WC: {exc}") from exc


def _load_finished_match_results(round_data: dict) -> dict[tuple[str, str], dict[str, Any]]:
    from config import settings
    from models.wc_prediction_meta import outcome_from_score

    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in load_wc_group_results(round_data):
        home = normalize_national_team(row["home_team"])
        away = normalize_national_team(row["away_team"])
        hs, as_ = int(row["home_score"]), int(row["away_score"])
        index[(home, away)] = {
            "actual_score": f"{hs}x{as_}",
            "actual_outcome": outcome_from_score(hs, as_),
        }

    registry_path = settings.lake_root / "artifacts" / "superbet_finalized_events.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for entry in registry.get("events", {}).values():
                home = normalize_national_team(str(entry.get("home_team", "")))
                away = normalize_national_team(str(entry.get("away_team", "")))
                if not home or not away:
                    continue
                score_raw = str(entry.get("final_score", "")).replace(":", "x")
                if "x" not in score_raw:
                    continue
                parts = score_raw.split("x", 1)
                hs, as_ = int(parts[0]), int(parts[1])
                index[(home, away)] = {
                    "actual_score": f"{hs}x{as_}",
                    "actual_outcome": outcome_from_score(hs, as_),
                }
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    return index


def _build_wc_round_predictions(predictor, round_data: dict, *, matchday: int | None = None) -> list[WcPredictionResponse]:
    cache = _wc_round_cache()
    phase_default = round_data.get("phase", "group")
    matches = round_data.get("matches", [])
    if matchday is not None:
        matches = [m for m in matches if m.get("round") == matchday]

    predictions: list[WcPredictionResponse] = []
    dirty = False
    finished = _load_finished_match_results(round_data)

    for match in matches:
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        match_phase = match.get("phase", phase_default)
        key = cache.match_key(home, away, match_phase)
        actual = finished.get((home, away))

        cached = cache.get_cached(key)
        if cached is not None and actual is None:
            predictions.append(WcPredictionResponse(**cached))
            continue
        if cached is not None and actual is not None:
            if cached.get("actual_score") == actual.get("actual_score"):
                predictions.append(WcPredictionResponse(**cached))
                continue

        try:
            pred = predictor.predict(
                home, away, phase=match_phase,
                season=round_data.get("season", 2026),
                group_name=match.get("group"),
            )
            resp = wc_prediction_to_response(
                pred,
                actual_score=actual.get("actual_score") if actual else None,
                actual_outcome=actual.get("actual_outcome") if actual else None,
            )
            cache.set_cached(key, resp.model_dump())
            predictions.append(resp)
            dirty = True
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Erro ao prever {home} x {away}: {exc}"
            ) from exc

    if dirty:
        cache.persist_to_disk()

    return predictions


# ---------------------------------------------------------------------------
# Sofascore
# ---------------------------------------------------------------------------


@router.get("/sofascore/resolve", response_model=WcSofascoreResolveResponse)
def worldcup_sofascore_resolve(
    home_team: str = Query(...),
    away_team: str = Query(...),
    date: str = Query(..., description="Data do jogo (YYYY-MM-DD)"),
):
    from datetime import date as date_type

    from api.sofascore_http import ensure_sofascore_not_in_cooldown, raise_sofascore_http_error
    from ingest.sofascore.client import SofascoreClient
    from ingest.sofascore.event_helpers import find_event_id
    from ingest.sofascore.teams import event_team_names

    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    try:
        match_date = date_type.fromisoformat(date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Data inválida; use YYYY-MM-DD") from exc

    ensure_sofascore_not_in_cooldown()
    try:
        event = find_event_id(SofascoreClient(), home_team=home, away_team=away, match_date=match_date)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise_sofascore_http_error(exc)

    event_home, event_away = event_team_names(event)
    return WcSofascoreResolveResponse(
        event_id=int(event["id"]),
        home_team=home,
        away_team=away,
        match_date=match_date.isoformat(),
        sofascore_home=event_home or None,
        sofascore_away=event_away or None,
    )


@router.get("/sofascore/{event_id}/statistics", response_model=WcSofascoreStatsResponse)
def worldcup_sofascore_statistics(
    event_id: int,
    refresh: bool = Query(False),
):
    from datetime import datetime, timezone

    from api.sofascore_http import ensure_sofascore_not_in_cooldown, raise_sofascore_http_error
    from ingest.sofascore.stats_ingest import ingest_match_stats, load_match_stats

    _EXCLUDE = {"event_id", "home_team", "away_team", "match_date", "source", "fetched_at"}

    if not refresh:
        cached = load_match_stats(event_id)
        if cached:
            fetched_at = cached.get("fetched_at")
            if not isinstance(fetched_at, str):
                fetched_at = datetime.now(timezone.utc).isoformat()
            return WcSofascoreStatsResponse(
                event_id=int(cached["event_id"]),
                home_team=str(cached["home_team"]),
                away_team=str(cached["away_team"]),
                match_date=cached.get("match_date"),
                stats={k: v for k, v in cached.items() if k not in _EXCLUDE},
                fetched_at=fetched_at,
                cached=True,
            )

    ensure_sofascore_not_in_cooldown()
    try:
        result = ingest_match_stats(event_id=event_id, save=True)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise_sofascore_http_error(exc)

    payload = result.to_payload()
    return WcSofascoreStatsResponse(
        event_id=result.event_id,
        home_team=result.home_team,
        away_team=result.away_team,
        match_date=result.match_date,
        stats={k: v for k, v in payload.items() if k not in _EXCLUDE},
        fetched_at=str(payload["fetched_at"]),
        cached=False,
    )


# ---------------------------------------------------------------------------
# Corners
# ---------------------------------------------------------------------------


@router.post("/corners/predict", response_model=WcCornersPredictResponse)
def worldcup_corners_predict(req: WcCornersPredictRequest):
    from models.corners_predictor import CornersPredictor

    home = normalize_national_team(req.home_team)
    away = normalize_national_team(req.away_team)
    if req.phase == "group" and not official_match_exists(home, away, phase="group"):
        raise HTTPException(
            status_code=400,
            detail=f"Confronto {home} x {away} não consta na tabela oficial da fase de grupos.",
        )

    result = CornersPredictor().predict(home, away, phase=req.phase)
    pred = result.prediction
    factors = result.factors.as_dict()
    return WcCornersPredictResponse(
        home_team=result.home_team,
        away_team=result.away_team,
        data_source=result.data_source,
        expected_corners=f"{pred.expected_home_corners:.1f}x{pred.expected_away_corners:.1f}",
        expected_total_corners=round(pred.expected_total_corners, 2),
        most_likely_corners=pred.most_likely_score,
        prob_home_more_corners=round(pred.prob_home_more, 4),
        prob_draw_corners=round(pred.prob_draw_corners, 4),
        prob_away_more_corners=round(pred.prob_away_more, 4),
        line_probs={k: round(v, 4) for k, v in pred.line_probs.items()},
        factors=WcCornerFactors(**factors),
        training_summary=result.training_summary,
    )


# ---------------------------------------------------------------------------
# Predict / Simulate
# ---------------------------------------------------------------------------


@router.post("/predict", response_model=WcPredictionResponse)
def worldcup_predict(req: WcPredictRequest):
    from ingest.sofascore.client import SofascoreClientError
    from ingest.sofascore.kxl_merge import merge_sofascore_fept

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home = normalize_national_team(req.home_team)
    away = normalize_national_team(req.away_team)
    if req.phase == "group" and not official_match_exists(home, away, phase="group"):
        raise HTTPException(
            status_code=400,
            detail=f"Confronto {home} x {away} não consta na tabela oficial da fase de grupos.",
        )

    try:
        kxl_match, fept_meta = merge_sofascore_fept(
            kxl_match=req.kxl_match,
            sofascore_event_id=req.sofascore_event_id,
            home_team=home,
            away_team=away,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SofascoreClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        pred = predictor.predict(
            home, away, phase=req.phase, kxl_match=kxl_match, season=2026,
            group_name=lookup_2026_group(home, away) if req.phase == "group" else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = wc_prediction_to_response(pred)
    if fept_meta:
        response.model_breakdown.kxl_fept = fept_meta
    return response


@router.post("/simulate", response_model=WcSimulationResponse)
def worldcup_simulate(req: WcPredictRequest):
    from datetime import date as date_type

    from models.wc_match_simulator import simulate_match

    try:
        predictor = deps.get_wc_predictor()
    except ValueError:
        predictor = None

    home = normalize_national_team(req.home_team)
    away = normalize_national_team(req.away_team)
    parsed_date: date_type | None = None
    if req.match_date:
        try:
            parsed_date = date_type.fromisoformat(req.match_date[:10])
        except ValueError:
            raise HTTPException(status_code=400, detail="match_date inválida") from None

    try:
        result = simulate_match(
            home_team=home,
            away_team=away,
            match_date=parsed_date,
            phase=req.phase,
            is_neutral=True,
            season=2026,
            group_name=lookup_2026_group(home, away) if req.phase == "group" else None,
            predictor=predictor,
            fifa_match_id=req.fifa_match_id,
            sofascore_event_id=req.sofascore_event_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WcSimulationResponse(
        home_team=result.home_team,
        away_team=result.away_team,
        match_date=result.match_date,
        prediction=result.prediction,
        confidence=result.confidence,
        prob_home=result.prob_home,
        prob_draw=result.prob_draw,
        prob_away=result.prob_away,
        poisson_score=result.poisson_score,
        expected_goals=result.expected_goals,
        fifa_home_lineup=result.fifa_home_lineup,
        fifa_away_lineup=result.fifa_away_lineup,
        fifa_home_bench=result.fifa_home_bench,
        fifa_away_bench=result.fifa_away_bench,
        fifa_home_goals=result.fifa_home_goals,
        fifa_away_goals=result.fifa_away_goals,
        fifa_home_tactics=result.fifa_home_tactics,
        fifa_away_tactics=result.fifa_away_tactics,
        fifa_home_coach=result.fifa_home_coach,
        fifa_away_coach=result.fifa_away_coach,
        fifa_stadium=result.fifa_stadium,
        fifa_attendance=result.fifa_attendance,
        fifa_home_points=result.fifa_home_points,
        fifa_away_points=result.fifa_away_points,
        fifa_points_diff=result.fifa_points_diff,
        lineup_source=result.lineup_source,
        enrich_features=result.enrich_features,
        stats_features=result.stats_features,
        model_breakdown=result.model_breakdown,
        warnings=result.warnings,
    )


# ---------------------------------------------------------------------------
# Round / Group Standings
# ---------------------------------------------------------------------------


@router.get("/round", response_model=WcRoundResponse)
def worldcup_round(matchday: int | None = Query(None, alias="round", ge=1, le=3)):
    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    round_data = _load_wc_round()
    predictions = _build_wc_round_predictions(predictor, round_data, matchday=matchday)
    return WcRoundResponse(
        season=round_data.get("season", 2026),
        competition=round_data.get("competition", "Copa do Mundo"),
        phase=round_data.get("phase", "group"),
        round=matchday if matchday is not None else round_data.get("round", 0),
        predictions=predictions,
    )


@router.get("/group-standings", response_model=WcGroupStandingsResponse)
def worldcup_group_standings():
    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    round_data = _load_wc_round()
    predictions = _build_wc_round_predictions(predictor, round_data, matchday=None)
    pair_group: dict[tuple[str, str], str] = {}
    for match in round_data.get("matches", []):
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        g = match.get("group")
        if g:
            pair_group[(home, away)] = str(g)

    pred_rows = [
        {
            "home_team": pred.home_team,
            "away_team": pred.away_team,
            "prediction": pred.prediction,
            "group": pair_group.get((pred.home_team, pred.away_team)),
        }
        for pred in predictions
    ]

    groups_meta = round_data.get("groups", [])
    blocks = build_group_standings(groups_meta, pred_rows)
    real_results = load_wc_group_results(round_data)
    real_blocks = build_group_standings_from_results(groups_meta, real_results)
    blocks = merge_real_into_simulated(blocks, real_blocks)
    as_of = datetime.now(UTC).date().isoformat()
    note = (
        "Pts: projeção do modelo (3 rodadas). Pts R: placares reais até "
        f"{as_of} ({len(real_results)} jogos disputados)."
    )
    return WcGroupStandingsResponse(
        season=int(round_data.get("season", 2026)),
        competition=round_data.get("competition", "Copa do Mundo FIFA 2026"),
        simulated=True,
        note=note,
        as_of=as_of,
        n_real_results=len(real_results),
        groups=[WcGroupStandingsBlock(**block) for block in blocks],
    )


# ---------------------------------------------------------------------------
# Teams / Friendlies / Schedule / Squads
# ---------------------------------------------------------------------------


@router.get("/teams", response_model=WcTeamsResponse)
def worldcup_teams():
    from ingest.fixtures.world_cup import load_wc_fixtures

    fixtures = load_wc_fixtures()
    teams: set[str] = set()
    if not fixtures.empty:
        teams.update(fixtures["home_team"].dropna().unique())
        teams.update(fixtures["away_team"].dropna().unique())

    round_data = _load_wc_round()
    for match in round_data.get("matches", []):
        teams.add(normalize_national_team(match["home_team"]))
        teams.add(normalize_national_team(match["away_team"]))

    sorted_teams = sorted(teams, key=str.casefold)
    return WcTeamsResponse(teams=sorted_teams, count=len(sorted_teams))


@router.get("/friendlies", response_model=WcFriendliesResponse)
def worldcup_friendlies(
    team: str = Query(...),
    pages: int = Query(2, ge=1, le=5),
    year: int | None = Query(None, ge=2000, le=2100),
    include_finished: bool = Query(True),
    include_upcoming: bool = Query(True),
):
    from ingest.sofascore.client import SofascoreClient, SofascoreClientError
    from ingest.sofascore.friendlies import list_team_friendlies, save_friendlies_snapshot

    canonical = normalize_national_team(team)
    filter_year = year if year is not None else datetime.now(timezone.utc).year
    try:
        friendlies = list_team_friendlies(
            canonical, pages=pages, year=filter_year,
            include_finished=include_finished, include_upcoming=include_upcoming,
            client=SofascoreClient(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SofascoreClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        save_friendlies_snapshot(canonical, filter_year, friendlies)
    except OSError:
        pass

    return WcFriendliesResponse(
        team=canonical,
        year=filter_year,
        count=len(friendlies),
        friendlies=[WcFriendlyItem(**row.to_dict()) for row in friendlies],
    )


@router.get("/schedule", response_model=WcScheduleResponse)
def worldcup_schedule():
    try:
        data = load_wc_schedule()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Calendário WC inválido: {exc}") from exc

    payload = build_schedule_response(data)
    return WcScheduleResponse(**payload)


@router.get("/squads", response_model=WcSquadTeamsResponse)
def worldcup_squads():
    try:
        data = load_wc_squads()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Convocações WC inválidas: {exc}") from exc

    return WcSquadTeamsResponse(
        season=data.get("season", 2026),
        competition=data.get("competition", "Copa do Mundo FIFA 2026"),
        source_url=data.get("source_url", ""),
        updated_at=data.get("updated_at", ""),
        team_count=data.get("team_count", len(data.get("squads", []))),
        teams=list_squad_teams(data),
    )


@router.get("/squads/{team}", response_model=WcSquadDetailResponse)
def worldcup_squad_detail(team: str):
    try:
        data = load_wc_squads()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    squad = get_squad_by_team(data, team)
    if squad is None:
        raise HTTPException(status_code=404, detail=f"Convocação não encontrada: {team}")

    return WcSquadDetailResponse(
        season=data.get("season", 2026),
        competition=data.get("competition", "Copa do Mundo FIFA 2026"),
        source_url=data.get("source_url", ""),
        updated_at=data.get("updated_at", ""),
        squad=WcSquadTeamItem(**squad),
    )


# ---------------------------------------------------------------------------
# Editions / Validate / Walkforward
# ---------------------------------------------------------------------------


@router.get("/editions", response_model=WcEditionsResponse)
def worldcup_editions():
    from pipelines.wc_validate import list_wc_editions

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    editions = list_wc_editions(predictor.fixtures)
    return WcEditionsResponse(editions=[WcEditionItem(**e) for e in editions])


@router.get("/editions/{season}/matches", response_model=WcEditionMatchesResponse)
def worldcup_edition_matches(season: int):
    from pipelines.wc_validate import list_edition_matches

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    matches = list_edition_matches(predictor.fixtures, season)
    if not matches:
        raise HTTPException(status_code=404, detail=f"Nenhum jogo encontrado para a edição {season}")
    return WcEditionMatchesResponse(
        season=season,
        matches=[WcHistoricalMatchItem(**sanitize_match_item(m)) for m in matches],
    )


@router.post("/validate", response_model=WcValidateResponse)
def worldcup_validate(req: WcValidateRequest):
    from pipelines.wc_validate import validate_historical_match

    if not req.match_id and (not req.home_team or not req.away_team):
        raise HTTPException(status_code=400, detail="Informe match_id ou home_team e away_team")

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home = normalize_national_team(req.home_team) if req.home_team else None
    away = normalize_national_team(req.away_team) if req.away_team else None

    try:
        result = validate_historical_match(
            predictor, predictor.fixtures, req.season,
            match_id=req.match_id, home_team=home, away_team=away,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return WcValidateResponse(
        match=WcValidateMatchInfo(**result["match"]),
        prediction=result["prediction"],
        confidence=round(result["confidence"], 4),
        prob_home=round(result["prob_home"], 4),
        prob_draw=round(result["prob_draw"], 4),
        prob_away=round(result["prob_away"], 4),
        poisson_score=result["poisson_score"],
        expected_goals=result["expected_goals"],
        correct=result["correct"],
        context=result["context"],
        h2h_summary=result["h2h_summary"],
        model_breakdown=breakdown_to_response(result["model_breakdown"]),
        cutoff_date=result["cutoff_date"],
        cutoff_note=result["cutoff_note"],
    )


@router.get("/walkforward")
def worldcup_walkforward():
    from config import settings

    report_path = settings.lake_root / "reports" / "wc_walkforward_report.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=404, detail="Relatório ausente. Execute: walkforward-wc-models"
        )
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/benchmarks/history")
def worldcup_benchmark_history():
    from pipelines.model_benchmark_history import history_with_deltas

    payload = history_with_deltas()
    if not payload.get("snapshots"):
        raise HTTPException(
            status_code=404, detail="Histórico ausente. Execute: run-model-benchmark --seed-only"
        )
    return payload


@router.get("/models/registry")
def worldcup_models_registry():
    from pipelines.mlflow_registry import model_registry_summary

    return model_registry_summary()


@router.get("/inplay/ensemble-status")
def worldcup_inplay_ensemble_status(
    user_id: str = Query(default="jamarorn"),
):
    from pipelines.inplay_ensemble_readiness import assess_ensemble_readiness

    return assess_ensemble_readiness(user_id).to_dict()


# ---------------------------------------------------------------------------
# Train / Retrain
# ---------------------------------------------------------------------------


@router.get("/train/status")
def worldcup_train_status():
    from dataclasses import asdict

    from models.wc_train_progress import read_train_progress

    state = read_train_progress()
    with deps._wc_train_lock:
        thread_alive = deps._wc_train_thread is not None and deps._wc_train_thread.is_alive()
    if state is None:
        return {"status": "running" if thread_alive else "idle", "running": thread_alive}
    payload = asdict(state)
    payload["running"] = thread_alive or state.status == "running"
    return payload


def _run_wc_retrain_background(*, enable_mlflow: bool = False) -> None:

    from models.wc_artifact import load_or_train_wc_predictor
    from models.wc_train_progress import WcTrainProgressReporter

    reporter = WcTrainProgressReporter(console=False)
    try:
        predictor, manifest = load_or_train_wc_predictor(force=True, progress=reporter, enable_mlflow=enable_mlflow)
        with deps._wc_train_lock:
            deps._wc_predictor = predictor
            deps._wc_artifact_meta = manifest
            deps._wc_models_ready = True
        _wc_round_cache().invalidate_wc_round_cache()
    except Exception as exc:
        with deps._wc_train_lock:
            deps._wc_models_ready = False
        reporter.fail(str(exc))
    finally:
        with deps._wc_train_lock:
            deps._wc_train_thread = None


@router.post("/retrain")
def worldcup_retrain(
    background: bool = Query(False),
    mlflow: bool = Query(False),
):
    import threading

    if background:
        with deps._wc_train_lock:
            if deps._wc_train_thread is not None and deps._wc_train_thread.is_alive():
                raise HTTPException(status_code=409, detail="Treino WC já em andamento")
            deps._wc_train_thread = threading.Thread(
                target=_run_wc_retrain_background,
                kwargs={"enable_mlflow": mlflow},
                name="wc-retrain",
                daemon=True,
            )
            deps._wc_train_thread.start()
        return {"status": "started", "poll": "/worldcup/train/status", "mlflow": mlflow}

    try:
        from models.wc_artifact import load_or_train_wc_predictor
        from models.wc_train_progress import WcTrainProgressReporter

        reporter = WcTrainProgressReporter(console=False)
        predictor, meta = load_or_train_wc_predictor(force=True, progress=reporter, enable_mlflow=mlflow)
        deps._wc_predictor = predictor
        deps._wc_artifact_meta = meta
        deps._wc_models_ready = True
        _wc_round_cache().invalidate_wc_round_cache()
    except ValueError as exc:
        deps._wc_models_ready = False
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok", "artifact": deps._wc_artifact_meta}


# ---------------------------------------------------------------------------
# Value / Combo Ticket
# ---------------------------------------------------------------------------


@router.post("/value/live", response_model=WcValueResponse)
def worldcup_live_value(req: WcValueRequest):
    from ingest.odds.the_odds_api import fetch_live_h2h_odds, merge_schedule_with_odds, save_odds_file as _save_odds
    from models.ev_value import evaluate_match

    schedule_path = Path(req.schedule_file)
    if not schedule_path.exists():
        raise HTTPException(status_code=404, detail=f"Schedule não encontrado: {schedule_path}")

    try:
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler schedule: {exc}") from exc

    try:
        live_odds = fetch_live_h2h_odds(
            sport_key=req.sport_key, regions=req.regions, preferred_bookmaker=req.bookmaker
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Odds API: {exc}") from exc

    merged, matched = merge_schedule_with_odds(schedule, live_odds)
    if req.save_odds_file:
        _save_odds(merged, Path(req.output_odds_file))

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    from api.helpers import match_value_to_response

    phase_default = merged.get("phase", "group")
    reports = []
    for match in merged.get("matches", []):
        phase = match.get("phase", phase_default)
        pred = predictor.predict(match["home_team"], match["away_team"], phase=phase)
        value = evaluate_match(
            home_team=match["home_team"],
            away_team=match["away_team"],
            probabilities={"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away},
            odds=match["odds"],
            min_edge=req.min_edge,
        )
        reports.append(match_value_to_response(value))

    return WcValueResponse(
        matched_games=matched,
        total_schedule_games=len(schedule.get("matches", [])),
        source=merged.get("source", "the-odds-api"),
        captured_at=merged.get("captured_at"),
        edges=reports,
    )


@router.get("/surebet/scan", response_model=SurebetScanResponse)
async def worldcup_surebet_scan(
    home: str | None = Query(None, description="Filtrar por mandante"),
    away: str | None = Query(None, description="Filtrar por visitante"),
    sport_key: str | None = Query(None),
    regions: str | None = Query(None, description="Regiões Odds API: eu, us, uk, au (separar por vírgula)"),
    bankroll: float = Query(1000, gt=0),
    min_margin_pct: float | None = Query(None, ge=0, le=20),
    superbet_event_id: int | None = Query(
        None,
        description="Inclui odds Superbet BR no scan (event_id ao vivo)",
    ),
):
    """Varre múltiplas casas (The Odds API) em busca de surebet 1X2."""
    from config import settings
    from ingest.odds.the_odds_api import fetch_multi_bookmaker_h2h
    from models.surebet import scan_h2h_surebets
    from schemas.national_teams import normalize_national_team

    margin = min_margin_pct if min_margin_pct is not None else settings.surebet_min_margin_pct

    try:
        events = await asyncio.to_thread(
            fetch_multi_bookmaker_h2h,
            sport_key=sport_key,
            regions=regions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Odds API: {exc}") from exc

    superbet_quote: dict[str, object] | None = None
    if superbet_event_id is not None:
        from ingest.superbet.client import SuperbetClient, SuperbetClientError

        try:
            snap = await asyncio.to_thread(SuperbetClient().fetch_event, superbet_event_id)
            if snap.h2h_odds:
                superbet_quote = {
                    "bookmaker": "superbet",
                    "odds": dict(snap.h2h_odds),
                }
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    payload_events: list[dict[str, object]] = []
    bookmakers_seen: set[str] = set()

    home_n = normalize_national_team(home) if home else None
    away_n = normalize_national_team(away) if away else None

    for event in events:
        if home_n and event.home_team != home_n:
            continue
        if away_n and event.away_team != away_n:
            continue

        quotes = event.to_quotes_dict()
        for q in quotes:
            bookmakers_seen.add(str(q["bookmaker"]))

        if superbet_quote and (
            (not home_n or event.home_team == home_n)
            and (not away_n or event.away_team == away_n)
        ):
            quotes = [*quotes, superbet_quote]
            bookmakers_seen.add("superbet")

        payload_events.append({
            "home_team": event.home_team,
            "away_team": event.away_team,
            "commence_time": event.commence_time,
            "quotes": quotes,
        })

    opportunities = scan_h2h_surebets(
        payload_events,
        bankroll=bankroll,
        min_margin_pct=margin,
    )

    return SurebetScanResponse(
        source="the-odds-api+superbet" if superbet_quote else "the-odds-api",
        regions=regions or settings.odds_default_regions,
        bookmakers_seen=len(bookmakers_seen),
        events_scanned=len(payload_events),
        opportunities=[SurebetOpportunityResponse(**opp.to_dict()) for opp in opportunities],
        note=(
            "Surebet = soma(1/odd) < 1 entre casas diferentes. "
            "Oportunidades reais são raras e expiram em minutos. "
            "Configure ODDS_API_KEY e use regions=eu,us,uk para mais casas."
        ),
    )


@router.get("/combo-ticket")
async def worldcup_combo_ticket(
    home_team: str = Query(...),
    away_team: str = Query(...),
    bankroll: float = Query(1000, gt=0),
    superbet_event_id: int | None = Query(None),
):
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from models.wc_team_patterns import build_combo_ticket

    snapshot = None
    if superbet_event_id is not None:
        try:
            snapshot = await asyncio.to_thread(SuperbetClient().fetch_event, superbet_event_id)
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return build_combo_ticket(home_team, away_team, bankroll=bankroll, snapshot=snapshot)


# ---------------------------------------------------------------------------
# Pré-jogo
# ---------------------------------------------------------------------------


@router.get("/pregame/today")
def pregame_today(
    days_ahead: int = Query(1, ge=1, le=7),
    days_back: int = Query(0, ge=0, le=3),
    tz: str = Query("America/Sao_Paulo", description="Fuso para definir 'hoje' na sidebar"),
    today_only: bool = Query(
        True,
        description="Somente jogos do dia local (+ madrugada nas próximas 8h)",
    ),
):
    import structlog
    from zoneinfo import ZoneInfo

    from pipelines.wc_pregame_today import build_pregame_window, match_status

    logger = structlog.get_logger()

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    schedule = load_wc_schedule()
    now = datetime.now(timezone.utc)
    window_matches, meta = build_pregame_window(
        schedule,
        now=now,
        tz_name=tz,
        days_ahead=days_ahead,
        days_back=days_back,
        today_only=today_only,
    )

    results = []
    for ko, m in window_matches:
        home = normalize_national_team(m["home_team"])
        away = normalize_national_team(m["away_team"])
        phase = m.get("phase", "group")
        group_name = lookup_2026_group(home, away) if phase == "group" else None
        played = m.get("home_score") is not None and m.get("away_score") is not None

        pred_payload: dict[str, Any]
        try:
            pred = predictor.predict(home, away, phase=phase, season=2026, group_name=group_name)
            pred_payload = {
                "prob_home": round(pred.prob_home, 4),
                "prob_draw": round(pred.prob_draw, 4),
                "prob_away": round(pred.prob_away, 4),
                "prediction": pred.prediction,
                "confidence": round(pred.confidence, 4),
                "poisson_score": pred.poisson_score,
                "expected_goals": pred.expected_goals,
                "predict_error": None,
            }
        except Exception as exc:
            logger.warning("pregame_predict_fallback", home=home, away=away, error=str(exc))
            pred_payload = {
                "prob_home": 0.33,
                "prob_draw": 0.34,
                "prob_away": 0.33,
                "prediction": "X",
                "confidence": 0.34,
                "poisson_score": "1x1",
                "expected_goals": "1.3x1.1",
                "predict_error": str(exc)[:160],
            }

        local_date = ko.astimezone(ZoneInfo(tz)).date().isoformat()
        results.append({
            "id": m.get("id", f"{home}-{away}"),
            "home_team": home,
            "away_team": away,
            "kickoff_utc": ko.isoformat(),
            "kickoff_local": m["kickoff"],
            "kickoff_date": local_date,
            "venue": m.get("venue"),
            "city": m.get("city"),
            "group": m.get("group"),
            "phase": phase,
            "played": played,
            "status": match_status(ko, m, now=now),
            "home_score": m.get("home_score"),
            "away_score": m.get("away_score"),
            **pred_payload,
        })

    return {
        **meta,
        "total": len(results),
        "matches": results,
    }


@router.get("/pregame/analysis")
def pregame_analysis(
    home: str = Query(...),
    away: str = Query(...),
    phase: str = Query("group"),
):
    from ingest.superbet.match_context_store import load_match_context
    from dateutil.parser import parse as parse_dt
    from zoneinfo import ZoneInfo

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home_n = normalize_national_team(home)
    away_n = normalize_national_team(away)
    group_name = lookup_2026_group(home_n, away_n) if phase == "group" else None

    try:
        pred = predictor.predict(home_n, away_n, phase=phase, season=2026, group_name=group_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        parts = pred.expected_goals.split("x")
        lam_home, lam_away = float(parts[0]), float(parts[1])
    except Exception:
        lam_home, lam_away = 1.3, 0.9

    MAX_G = 5
    scorelines = []
    total_mass = 0.0
    for i in range(MAX_G + 1):
        for j in range(MAX_G + 1):
            p_h = (lam_home**i * math.exp(-lam_home)) / math.factorial(i)
            p_a = (lam_away**j * math.exp(-lam_away)) / math.factorial(j)
            p = p_h * p_a
            total_mass += p
            scorelines.append({"score": f"{i}x{j}", "prob": p})
    for s in scorelines:
        s["prob"] = round(s["prob"] / total_mass, 4)
    scorelines.sort(key=lambda x: x["prob"], reverse=True)

    prob_over_15 = sum(s["prob"] for s in scorelines if sum(int(x) for x in s["score"].split("x")) > 1)
    prob_over_25 = sum(s["prob"] for s in scorelines if sum(int(x) for x in s["score"].split("x")) > 2)
    prob_over_35 = sum(s["prob"] for s in scorelines if sum(int(x) for x in s["score"].split("x")) > 3)
    prob_btts = sum(s["prob"] for s in scorelines if int(s["score"].split("x")[0]) > 0 and int(s["score"].split("x")[1]) > 0)
    prob_home_hcap = sum(
        s["prob"] for s in scorelines
        if int(s["score"].split("x")[0]) - int(s["score"].split("x")[1]) >= 2
    )

    def _kelly(prob: float, odd: float) -> float:
        if odd <= 1.0 or prob <= 0:
            return 0.0
        edge = prob * odd - 1
        if edge <= 0:
            return 0.0
        return round(edge / (odd - 1) * 0.25 * 100, 1)

    def _conf_label(prob: float) -> str:
        return "Alta" if prob >= 0.70 else "Média" if prob >= 0.55 else "Baixa"

    raw_markets = [
        ("1", f"Vitória {home_n}", pred.prob_home),
        ("X", "Empate", pred.prob_draw),
        ("2", f"Vitória {away_n}", pred.prob_away),
        ("over_1_5", "Mais de 1.5 gols", round(prob_over_15, 4)),
        ("over_2_5", "Mais de 2.5 gols", round(prob_over_25, 4)),
        ("over_3_5", "Mais de 3.5 gols", round(prob_over_35, 4)),
        ("btts", "Ambas marcam", round(prob_btts, 4)),
        ("home_-1", f"{home_n} -1 Handicap", round(prob_home_hcap, 4)),
    ]

    picks = []
    for key, label, prob in raw_markets:
        fair_odd = round(1 / prob, 2) if prob > 0 else None
        picks.append({
            "market": key, "label": label, "model_prob": round(prob, 4),
            "fair_odd": fair_odd, "kelly_units": _kelly(prob, fair_odd) if fair_odd else 0.0,
            "confidence": _conf_label(prob),
        })

    ranked_picks = sorted([p for p in picks if p["model_prob"] >= 0.45], key=lambda x: x["model_prob"], reverse=True)
    ticket_singles = ranked_picks[:3]
    best_result = max([p for p in picks if p["market"] in ("1", "X", "2")], key=lambda x: x["model_prob"])
    best_over = next((p for p in picks if p["market"] in ("over_2_5", "over_1_5") and p["model_prob"] >= 0.55), None)
    combo = None
    if best_over:
        combo_prob = round(best_result["model_prob"] * best_over["model_prob"], 4)
        combo_fair_odd = round(1 / combo_prob, 2) if combo_prob > 0 else None
        combo = {
            "label": f"{best_result['label']} + {best_over['label']}",
            "markets": [best_result["market"], best_over["market"]],
            "model_prob": combo_prob, "fair_odd": combo_fair_odd,
            "kelly_units": _kelly(combo_prob, combo_fair_odd) if combo_fair_odd else 0.0,
            "confidence": _conf_label(combo_prob),
        }

    match_context = None
    schedule = load_wc_schedule()
    kickoff_utc = None
    kickoff_date = None
    kickoff_local = None
    venue = None
    city = None
    for m in schedule.get("matches", []):
        h = normalize_national_team(m.get("home_team", ""))
        a = normalize_national_team(m.get("away_team", ""))
        if h == home_n and a == away_n:
            kickoff_local = m.get("kickoff")
            if kickoff_local:
                ko = parse_dt(str(kickoff_local)).astimezone(ZoneInfo("America/Sao_Paulo"))
                kickoff_utc = ko.astimezone(UTC).isoformat()
                kickoff_date = ko.date().isoformat()
            venue = m.get("venue")
            city = m.get("city")
            eid = m.get("sofascore_event_id") or m.get("event_id")
            if eid:
                match_context = load_match_context(int(eid))
            break

    return {
        "home_team": home_n, "away_team": away_n, "phase": phase, "group": group_name,
        "kickoff_utc": kickoff_utc,
        "kickoff_date": kickoff_date,
        "kickoff_local": kickoff_local,
        "venue": venue,
        "city": city,
        "prediction": pred.prediction, "confidence": round(pred.confidence, 4),
        "prob_home": round(pred.prob_home, 4), "prob_draw": round(pred.prob_draw, 4), "prob_away": round(pred.prob_away, 4),
        "poisson_score": pred.poisson_score, "expected_goals": pred.expected_goals, "h2h_summary": pred.h2h_summary,
        "top_scorelines": scorelines[:8],
        "picks": picks,
        "ticket": {"singles": ticket_singles, "combo": combo, "note": "Odd justa = 1/prob_modelo."},
        "match_context": match_context,
    }


@router.get("/pregame/research")
async def pregame_research(
    home: str = Query(...),
    away: str = Query(...),
    phase: str = Query("group"),
    force_refresh: bool = Query(False),
):
    from typing import Any as _Any

    from ingest.research.gemini_synthesizer import GeminiError
    from ingest.research.gemini_synthesizer import synthesize_pregame_report as gemini_synthesize
    from ingest.research.moonshot_synthesizer import MoonshotError
    from ingest.research.moonshot_synthesizer import synthesize_pregame_report as moonshot_synthesize
    from ingest.research.perplexity_client import PerplexityError, search_pregame
    from ingest.research.research_cache import load_cached, save_cached

    home_n = normalize_national_team(home)
    away_n = normalize_national_team(away)

    if not force_refresh:
        cached = load_cached(home_n, away_n)
        if cached:
            cached["from_cache"] = True
            if cached.get("pregame_context") is None:
                _s = cached.get("synthesis") or {}
                _arb = _s.get("arbitro") or {}
                _arb_name = _arb.get("nome") if _arb.get("nome") not in (None, "Não divulgado", "") else None
                _lam = _arb.get("card_lambda")
                _pr = _arb.get("penalty_rate")
                if _lam is None and _arb.get("perfil"):
                    import re as _re
                    _m = _re.search(r"(\d+[.,]\d+)\s*cart[õo]es?/jogo", _arb["perfil"], _re.IGNORECASE)
                    if _m:
                        try:
                            _lam = float(_m.group(1).replace(",", "."))
                        except ValueError:
                            pass
                if _arb_name or _lam is not None:
                    from ingest.superbet.match_context_store import save_match_context_by_teams
                    _ctx = {k: v for k, v in {
                        "home_team": home_n, "away_team": away_n,
                        "referee_name": _arb_name,
                        "referee_card_lambda": float(_lam) if _lam is not None else None,
                        "referee_penalty_rate": float(_pr) if _pr is not None else None,
                        "source": "pregame_research",
                    }.items() if v is not None}
                    save_match_context_by_teams(home_n, away_n, _ctx)
                    cached["pregame_context"] = _ctx or None
            return cached

    try:
        predictor = deps.get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    group_name = lookup_2026_group(home_n, away_n) if phase == "group" else None
    try:
        pred = await asyncio.to_thread(
            predictor.predict, home_n, away_n, phase=phase, season=2026, group_name=group_name
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        parts = pred.expected_goals.split("x")
        lam_home, lam_away = float(parts[0]), float(parts[1])
    except Exception:
        lam_home, lam_away = 1.3, 0.9

    MAX_G = 5
    scorelines, total_mass = [], 0.0
    for i in range(MAX_G + 1):
        for j in range(MAX_G + 1):
            p = (math.exp(-lam_home) * lam_home**i / math.factorial(i)) * (math.exp(-lam_away) * lam_away**j / math.factorial(j))
            total_mass += p
            scorelines.append({"score": f"{i}x{j}", "prob": p})
    for s in scorelines:
        s["prob"] = round(s["prob"] / total_mass, 4)
    scorelines.sort(key=lambda x: x["prob"], reverse=True)

    prob_over_25 = sum(s["prob"] for s in scorelines if sum(int(x) for x in s["score"].split("x")) > 2)
    prob_btts = sum(s["prob"] for s in scorelines if int(s["score"].split("x")[0]) > 0 and int(s["score"].split("x")[1]) > 0)

    def _kelly_r(p: float, odd: float) -> float:
        edge = p * odd - 1
        return round(max(0.0, edge / (odd - 1)) * 0.25 * 100, 1) if odd > 1 and p > 0 else 0.0

    singles = []
    for label, key, prob in [
        (f"Vitória {home_n}", "1", pred.prob_home), ("Empate", "X", pred.prob_draw),
        (f"Vitória {away_n}", "2", pred.prob_away),
        ("Mais de 2.5 gols", "over_2_5", round(prob_over_25, 4)),
        ("Ambas marcam", "btts", round(prob_btts, 4)),
    ]:
        fo = round(1 / prob, 2) if prob > 0 else None
        singles.append({"label": label, "market": key, "model_prob": round(prob, 4),
                        "fair_odd": fo, "kelly_units": _kelly_r(prob, fo) if fo else 0.0})

    best_result = max([s for s in singles if s["market"] in ("1", "X", "2")], key=lambda x: x["model_prob"])
    best_over = next((s for s in singles if s["market"] == "over_2_5" and s["model_prob"] >= 0.5), None)
    combo = None
    if best_over:
        cp = round(best_result["model_prob"] * best_over["model_prob"], 4)
        cfo = round(1 / cp, 2)
        combo = {"label": f"{best_result['label']} + {best_over['label']}",
                 "model_prob": cp, "fair_odd": cfo, "kelly_units": _kelly_r(cp, cfo)}

    from config import settings as _settings

    model_data = {
        "prob_home": round(pred.prob_home, 4), "prob_draw": round(pred.prob_draw, 4), "prob_away": round(pred.prob_away, 4),
        "confidence": round(pred.confidence, 4), "prediction": pred.prediction,
        "poisson_score": pred.poisson_score, "expected_goals": pred.expected_goals,
        "h2h_summary": pred.h2h_summary, "group": group_name, "phase": phase,
        "top_scorelines": scorelines[:6], "ticket": {"singles": singles, "combo": combo},
    }

    web_text = ""
    web_citations: list = []
    errors: dict[str, str] = {}
    _pplx_key = _settings.perplexity_api_key or ""
    if _pplx_key and not _pplx_key.startswith("pplx-CHAVE") and len(_pplx_key) > 30:
        try:
            sonar = await asyncio.to_thread(search_pregame, home_n, away_n)
            web_text = sonar["text"]
            web_citations = sonar.get("citations", [])
        except PerplexityError as exc:
            errors["perplexity"] = str(exc)

    synthesis: dict | None = None
    used_provider = ""
    provider_citations: list = []

    if _settings.gemini_api_key:
        try:
            result = await asyncio.to_thread(gemini_synthesize, home_n, away_n, model_data, web_text)
            synthesis = result["report"]
            provider_citations = result.get("web_searches", [])
            used_provider = f"gemini:{result.get('model', _settings.gemini_model)}"
        except GeminiError as exc:
            errors["gemini"] = str(exc)

    if synthesis is None and _settings.moonshot_api_key:
        try:
            result = await asyncio.to_thread(moonshot_synthesize, home_n, away_n, model_data, web_text)
            synthesis = result["report"]
            provider_citations = result.get("web_searches", [])
            used_provider = f"moonshot:{result.get('model', _settings.moonshot_model)}"
        except MoonshotError as exc:
            errors["moonshot"] = str(exc)

    if synthesis is None:
        from models.wc_local_synthesis import generate_local_synthesis_with_context_lookup
        local_synthesis = generate_local_synthesis_with_context_lookup(home_n, away_n, model_data, event_id=None)
        if local_synthesis:
            synthesis = local_synthesis
            used_provider = "local:match_context+model"

    pregame_context: dict[str, _Any] | None = None
    if synthesis:
        arb = synthesis.get("arbitro") or {}
        arb_name = arb.get("nome") if arb.get("nome") not in (None, "Não divulgado", "") else None
        card_lambda = arb.get("card_lambda")
        penalty_rate = arb.get("penalty_rate")
        if card_lambda is None and arb.get("perfil"):
            import re as _re
            m_lam = _re.search(r"(\d+[.,]\d+)\s*cart[õo]es?/jogo", arb["perfil"], _re.IGNORECASE)
            if m_lam:
                try:
                    card_lambda = float(m_lam.group(1).replace(",", "."))
                except ValueError:
                    pass
        if arb_name or card_lambda is not None:
            from ingest.superbet.match_context_store import save_match_context_by_teams
            pregame_context = {
                "home_team": home_n, "away_team": away_n,
                "referee_name": arb_name,
                "referee_card_lambda": float(card_lambda) if card_lambda is not None else None,
                "referee_penalty_rate": float(penalty_rate) if penalty_rate is not None else None,
                "home_pregame_xg": lam_home, "away_pregame_xg": lam_away,
                "source": "pregame_research",
            }
            pregame_context = {k: v for k, v in pregame_context.items() if v is not None}
            save_match_context_by_teams(home_n, away_n, pregame_context)

    payload: dict[str, _Any] = {
        "home_team": home_n, "away_team": away_n, "phase": phase, "group": group_name,
        "model_data": model_data, "web_research": {"text": web_text, "citations": web_citations + provider_citations},
        "synthesis": synthesis, "provider": used_provider, "errors": errors,
        "from_cache": False, "pregame_context": pregame_context,
    }

    if synthesis:
        save_cached(home_n, away_n, payload)

    return payload


def _pregame_synthesis_cached(home_n: str, away_n: str) -> dict[str, Any] | None:
    from ingest.research.research_cache import load_cached

    cached = load_cached(home_n, away_n)
    if not cached:
        return None
    syn = cached.get("synthesis")
    return syn if isinstance(syn, dict) else None


@router.get("/pregame/summary", response_model=PregameSummaryResponse)
def pregame_summary(
    home: str = Query(...),
    away: str = Query(...),
    phase: str = Query("group"),
):
    """Resumo IA curto para aba Bilhete (modelo + research em cache se existir)."""
    from models.pregame_llm import generate_pregame_summary

    analysis = pregame_analysis(home=home, away=away, phase=phase)
    synthesis = _pregame_synthesis_cached(analysis["home_team"], analysis["away_team"])
    result = generate_pregame_summary(analysis, synthesis)
    result["from_cache"] = synthesis is not None
    return PregameSummaryResponse(**result)


@router.get("/pregame/copilot", response_model=LiveCopilotResponse)
def pregame_copilot(
    home: str = Query(...),
    away: str = Query(...),
    phase: str = Query("group"),
):
    """Narrativa copiloto pré-jogo (requer OPENAI + LIVE_COPILOT_ENABLED)."""
    from models.pregame_llm import run_pregame_copilot

    analysis = pregame_analysis(home=home, away=away, phase=phase)
    synthesis = _pregame_synthesis_cached(analysis["home_team"], analysis["away_team"])
    payload = run_pregame_copilot(analysis, synthesis)
    return LiveCopilotResponse(**payload)


@router.post("/pregame/copilot/agent", response_model=LiveCopilotAgentResponse)
async def pregame_copilot_agent(req: PregameCopilotAgentRequest):
    """Chat agente pré-jogo — consulta modelo e Deep Research."""
    from models.pregame_llm import run_pregame_copilot_agent

    analysis = await asyncio.to_thread(
        pregame_analysis,
        home=req.home,
        away=req.away,
        phase=req.phase,
    )
    synthesis = _pregame_synthesis_cached(analysis["home_team"], analysis["away_team"])
    history = [{"role": m.role, "content": m.content} for m in req.history]
    payload = await asyncio.to_thread(
        run_pregame_copilot_agent,
        analysis,
        synthesis,
        req.message,
        history,
    )
    return LiveCopilotAgentResponse(**payload)
