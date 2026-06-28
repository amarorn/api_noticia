"""Rotas de notícias: feed, cards, sync, context e previsão baseline."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.lake_cache import invalidate_lake_counts
from api.schemas import (
    MatchContextResponse,
    MatchRequest,
    NewsArticleItem,
    NewsCardsResponse,
    NewsFeedResponse,
    NewsSourceItem,
    NewsSyncResponse,
    RoundPrediction,
    RoundResponse,
)
from config import settings
from pipelines.news_feed import build_news_all, build_news_cards, build_news_feed, resolve_news_teams
from pipelines.silver import load_silver
from schemas.national_teams import normalize_national_team

router = APIRouter()


@router.post("/news/sync", response_model=NewsSyncResponse)
async def news_sync(
    full_rebuild: bool = Query(False),
    fetch_body: bool | None = Query(None),
):
    from api.data_pulse import invalidate_pulse_meta_cache
    from ingest.news_sync import sync_news_sources

    do_fetch = settings.news_sync_fetch_body if fetch_body is None else fetch_body
    try:
        result = await sync_news_sources(
            fetch_body=do_fetch,
            run_silver=True,
            full_silver_rebuild=full_rebuild,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao sincronizar fontes: {exc}") from exc
    invalidate_lake_counts()
    invalidate_pulse_meta_cache()
    return NewsSyncResponse(**result)


@router.get("/news/feed", response_model=NewsFeedResponse)
async def news_feed(
    limit: int = 24,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
    days: int | None = 30,
):
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    if days is not None:
        days = min(max(days, 1), 365)

    silver_df = await asyncio.to_thread(load_silver)
    payload = await asyncio.to_thread(
        build_news_feed, silver_df, limit=limit, offset=offset, source=source, query=q, days=days
    )
    return NewsFeedResponse(
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
        sources=[NewsSourceItem(**s) for s in payload["sources"]],
        articles=[NewsArticleItem(**a) for a in payload["articles"]],
    )


@router.get("/news/all", response_model=NewsFeedResponse)
async def news_all(
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
    days: int | None = Query(None),
    team: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
    teams: str | None = Query(None, description="Brasil,Marrocos"),
):
    offset = max(offset, 0)
    if days is not None:
        days = min(max(days, 1), 3650)

    team_list: list[str] | None = None
    if teams:
        team_list = [t.strip() for t in teams.split(",") if t.strip()]

    resolved_teams = None
    if team_list or team or home_team or away_team:
        resolved_teams = resolve_news_teams(
            team=normalize_national_team(team) if team else None,
            home_team=normalize_national_team(home_team) if home_team else None,
            away_team=normalize_national_team(away_team) if away_team else None,
            teams=team_list,
        )

    silver_df = await asyncio.to_thread(load_silver)
    payload = await asyncio.to_thread(
        build_news_all, silver_df, offset=offset, source=source, query=q, days=days, teams=resolved_teams
    )
    return NewsFeedResponse(
        total=payload["total"],
        limit=len(payload["articles"]),
        offset=payload["offset"],
        sources=[NewsSourceItem(**s) for s in payload["sources"]],
        articles=[NewsArticleItem(**a) for a in payload["articles"]],
    )


@router.get("/news/cards", response_model=NewsCardsResponse)
async def news_cards(
    limit: int = 12,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
    days: int | None = 14,
    team: str | None = Query(None),
    home_team: str | None = Query(None),
    away_team: str | None = Query(None),
    teams: str | None = Query(None),
):
    limit = min(max(limit, 1), 48)
    offset = max(offset, 0)
    if days is not None:
        days = min(max(days, 1), 90)

    team_list: list[str] | None = None
    if teams:
        team_list = [t.strip() for t in teams.split(",") if t.strip()]

    silver_df = await asyncio.to_thread(load_silver)
    payload = await asyncio.to_thread(
        build_news_cards,
        silver_df,
        limit=limit,
        offset=offset,
        source=source,
        query=q,
        days=days,
        team=normalize_national_team(team) if team else None,
        home_team=normalize_national_team(home_team) if home_team else None,
        away_team=normalize_national_team(away_team) if away_team else None,
        teams=team_list,
    )
    return NewsCardsResponse(
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
        teams=payload["teams"],
        cards=[NewsArticleItem(**c) for c in payload["cards"]],
    )


@router.post("/context", response_model=MatchContextResponse)
def get_match_context(req: MatchRequest):
    from ingest.fixtures.brasileirao import load_fixtures
    from models.baseline import predict_baseline, predict_baseline_probs
    from pipelines.gold import build_gold_for_match

    silver_df = load_silver()
    fixtures_df = load_fixtures()
    match_id = f"{req.home_team}_{req.away_team}_{req.round_number}".lower().replace(" ", "_")
    context = build_gold_for_match(
        match_id=match_id,
        home_team=req.home_team,
        away_team=req.away_team,
        round_number=req.round_number,
        competition=req.competition,
        match_date=datetime.now(timezone.utc),
        silver_df=silver_df,
        season=req.season,
        fixtures_df=fixtures_df if not fixtures_df.empty else None,
        live_mode=True,
    )
    resp = MatchContextResponse(
        match_id=context.match_id,
        home_team=context.home_team,
        away_team=context.away_team,
        context_text=context.context_text,
        news_count_home=context.features.news_count_home,
        news_count_away=context.features.news_count_away,
        injury_mentions_home=context.features.injury_mentions_home,
        injury_mentions_away=context.features.injury_mentions_away,
        sentiment_home=context.features.sentiment_home,
        sentiment_away=context.features.sentiment_away,
        home_position=context.features.home_position,
        away_position=context.features.away_position,
        home_form=context.features.home_form,
        away_form=context.features.away_form,
    )
    return resp


@router.post("/predict", response_model=MatchContextResponse)
def predict_match(req: MatchRequest):
    from ingest.fixtures.brasileirao import load_fixtures
    from models.baseline import predict_baseline, predict_baseline_probs
    from pipelines.gold import build_gold_for_match

    silver_df = load_silver()
    fixtures_df = load_fixtures()
    match_id = f"{req.home_team}_{req.away_team}_{req.round_number}".lower().replace(" ", "_")
    context = build_gold_for_match(
        match_id=match_id,
        home_team=req.home_team,
        away_team=req.away_team,
        round_number=req.round_number,
        competition=req.competition,
        match_date=datetime.now(timezone.utc),
        silver_df=silver_df,
        season=req.season,
        fixtures_df=fixtures_df if not fixtures_df.empty else None,
        live_mode=True,
    )
    pred, conf, reason = predict_baseline(context.features)
    return MatchContextResponse(
        match_id=context.match_id,
        home_team=context.home_team,
        away_team=context.away_team,
        context_text=context.context_text,
        news_count_home=context.features.news_count_home,
        news_count_away=context.features.news_count_away,
        injury_mentions_home=context.features.injury_mentions_home,
        injury_mentions_away=context.features.injury_mentions_away,
        sentiment_home=context.features.sentiment_home,
        sentiment_away=context.features.sentiment_away,
        home_position=context.features.home_position,
        away_position=context.features.away_position,
        home_form=context.features.home_form,
        away_form=context.features.away_form,
        prediction=pred,
        confidence=conf,
        reason=reason,
        model_source="baseline",
        probabilities=predict_baseline_probs(context.features),
    )


@router.get("/round/predict", response_model=RoundResponse)
def predict_current_round():
    from pipelines.current_round import load_round_schedule, predict_round

    try:
        schedule = load_round_schedule()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    results = predict_round(save=False)
    return RoundResponse(
        round_number=schedule["round"],
        competition=schedule.get("competition", "Brasileirão"),
        predictions=[
            RoundPrediction(
                home_team=r["home_team"],
                away_team=r["away_team"],
                prediction=r["prediction"],
                confidence=r["confidence"],
                reason=r["reason"],
                news_count=r["news_count"],
            )
            for r in results
        ],
    )
