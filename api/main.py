import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.auth import ApiKeyMiddleware, api_key_enabled
from api.data_pulse import (
    DataPulseMiddleware,
    build_pulse_snapshot,
    invalidate_pulse_meta_cache,
)
from api.lake_cache import get_lake_counts, invalidate_lake_counts
from config import settings
from ingest.fixtures.brasileirao import load_fixtures
from ingest.odds.the_odds_api import fetch_live_h2h_odds, merge_schedule_with_odds, save_odds_file
from ingest.meta import collection_stats
from models.ev_value import MatchValueReport, evaluate_match
from models.baseline import predict_baseline, predict_baseline_probs

if TYPE_CHECKING:
    from models.wc_predictor import WcPrediction, WcPredictor
from schemas.wc_kxl_dynamic import WcKxlMatchInput
from pipelines.gold import build_gold_for_match
from ingest.news_sync import sync_news_sources
from pipelines.news_feed import (
    build_news_all,
    build_news_cards,
    build_news_feed,
    resolve_news_teams,
)
from pipelines.silver import load_silver
from pipelines.wc_squads import get_squad_by_team, list_squad_teams, load_wc_squads
from pipelines.wc_schedule import build_schedule_response, load_wc_schedule, official_match_exists
from pipelines.wc_group_pressure import lookup_2026_group
from pipelines.wc_group_standings import build_group_standings
from schemas.national_teams import normalize_national_team

WC_ROUND_FILE = Path("data/rounds/wc_2026.json")

_wc_models_ready = False
_wc_predictor: Any = None
_wc_artifact_meta: dict = {}


def _wc_round_cache():
    from api import wc_round_cache

    return wc_round_cache


def _warm_wc_models() -> None:
    global _wc_models_ready
    try:
        get_wc_predictor()
        _wc_round_cache().warm_from_disk()
        _wc_models_ready = True
    except ValueError:
        _wc_models_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carrega modelos WC em background para a API aceitar tráfego imediatamente (deploy/health)."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _warm_wc_models)
    yield


app = FastAPI(
    title="Bolão News API",
    description="API de contexto e previsão baseada em notícias esportivas",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Data-Pulse-At",
        "X-Articles-Silver",
        "X-Fixtures",
        "X-WC-Models-Ready",
        "X-Collections-Last-Run",
        "X-Latest-Silver-At",
    ],
)

app.add_middleware(
    DataPulseMiddleware,
    wc_models_ready=lambda: _wc_models_ready,
)

app.add_middleware(ApiKeyMiddleware)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    if api_key_enabled():
        schema.setdefault("components", {})["securitySchemes"] = {
            "ApiKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
            },
        }
        schema["security"] = [{"ApiKeyHeader": []}, {"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi


def get_wc_predictor(*, force: bool = False) -> "WcPredictor":
    global _wc_predictor, _wc_artifact_meta
    from models.wc_artifact import load_or_train_wc_predictor

    if force or _wc_predictor is None:
        _wc_predictor, _wc_artifact_meta = load_or_train_wc_predictor(
            force=force or settings.wc_artifact_force_retrain
        )
    return _wc_predictor


def _get_wc_predictor() -> "WcPredictor":
    return get_wc_predictor()


class MatchRequest(BaseModel):
    home_team: str = Field(..., examples=["Flamengo"])
    away_team: str = Field(..., examples=["Palmeiras"])
    round_number: int = Field(1, ge=1)
    competition: str = Field("Brasileirão", examples=["Brasileirão"])
    season: int | None = None


class MatchContextResponse(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    context_text: str
    news_count_home: int
    news_count_away: int
    injury_mentions_home: int
    injury_mentions_away: int
    sentiment_home: float | None
    sentiment_away: float | None
    home_position: int | None = None
    away_position: int | None = None
    home_form: str | None = None
    away_form: str | None = None
    prediction: str | None = None
    confidence: float | None = None
    reason: str | None = None
    model_source: str | None = None
    probabilities: dict[str, float] | None = None


class RoundPrediction(BaseModel):
    home_team: str
    away_team: str
    prediction: str
    confidence: float
    reason: str
    news_count: int


class RoundResponse(BaseModel):
    round_number: int
    competition: str
    predictions: list[RoundPrediction]


class WcValueRequest(BaseModel):
    schedule_file: str = Field("data/rounds/wc_2026.json", examples=["data/rounds/wc_2026.json"])
    output_odds_file: str = Field(
        "data/rounds/wc_2026_odds.json",
        examples=["data/rounds/wc_2026_odds.json"],
    )
    sport_key: str | None = Field(None, examples=["soccer_fifa_world_cup"])
    bookmaker: str | None = Field(None, examples=["bet365"])
    regions: str | None = Field(None, examples=["eu"])
    min_edge: float = Field(0.03, ge=0.0, le=1.0)
    save_odds_file: bool = True


class WcOutcomeValue(BaseModel):
    outcome: str
    odd: float
    model_prob: float
    implied_prob: float
    expected_value: float
    fair_odd: float
    kelly_quarter: float


class WcMatchValueResponse(BaseModel):
    home_team: str
    away_team: str
    best: WcOutcomeValue | None = None
    outcomes: list[WcOutcomeValue]


class WcValueResponse(BaseModel):
    matched_games: int
    total_schedule_games: int
    source: str
    captured_at: str | None = None
    edges: list[WcMatchValueResponse]


class WcPredictRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Marrocos"])
    phase: str = Field("group", examples=["group"])
    kxl_match: WcKxlMatchInput | None = Field(
        None,
        description="Entrada dinâmica KXL (FECL, FEJU, FEDE, FEPT, FEEM) — opcional",
    )


class WcGoalFactors(BaseModel):
    league_avg: float
    home_attack: float
    away_attack: float
    home_defense: float
    away_defense: float
    home_advantage: float
    elo_factor_home: float
    elo_factor_away: float
    lambda_home: float
    lambda_away: float
    rho: float


class WcModelBreakdown(BaseModel):
    dixon_coles: dict[str, float]
    logistic: dict[str, float]
    dixon_coles_rho: float | None = None
    poisson_factors: WcGoalFactors | None = None
    holdout_2022_accuracy: float | None = None
    ensemble_weights: dict[str, float]
    ensemble_brier: float | None = None
    kxl_baseline: dict | None = None
    kxl_collision: dict | None = None
    kxl_dynamic: dict | None = None


class WcPredictionResponse(BaseModel):
    home_team: str
    away_team: str
    prediction: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    poisson_score: str
    expected_goals: str
    context: str
    h2h_summary: str
    model_breakdown: WcModelBreakdown


class WcRoundResponse(BaseModel):
    season: int
    competition: str
    phase: str
    round: int
    predictions: list[WcPredictionResponse]


class WcGroupStandingRow(BaseModel):
    position: int
    team: str
    played: int
    won: int
    drawn: int
    lost: int
    gf: int
    ga: int
    gd: int
    points: int


class WcGroupStandingsBlock(BaseModel):
    group: str
    standings: list[WcGroupStandingRow]


class WcGroupStandingsResponse(BaseModel):
    season: int
    competition: str
    simulated: bool = True
    note: str
    groups: list[WcGroupStandingsBlock]


class WcTeamsResponse(BaseModel):
    teams: list[str]
    count: int


class WcScheduleGroup(BaseModel):
    id: str
    teams: list[str]


class WcScheduleMatchItem(BaseModel):
    match_id: str
    home_team: str
    away_team: str
    group: str | None = None
    round: int
    phase: str
    kickoff: str | None = None
    venue: str | None = None
    city: str | None = None


class WcScheduleResponse(BaseModel):
    season: int
    competition: str
    phase: str
    groups: list[WcScheduleGroup]
    matchdays: list[int]
    matches: list[WcScheduleMatchItem]
    total_matches: int


class WcSquadPlayerItem(BaseModel):
    name: str
    club: str | None = None


class WcSquadSectionItem(BaseModel):
    role: str
    position: str
    players: list[WcSquadPlayerItem]


class WcSquadTeamItem(BaseModel):
    team: str
    player_count: int
    sections: list[WcSquadSectionItem]


class WcSquadTeamsResponse(BaseModel):
    season: int
    competition: str
    source_url: str
    updated_at: str
    team_count: int
    teams: list[dict]


class WcSquadDetailResponse(BaseModel):
    season: int
    competition: str
    source_url: str
    updated_at: str
    squad: WcSquadTeamItem


class WcEditionItem(BaseModel):
    season: int
    label: str
    match_count: int


class WcEditionsResponse(BaseModel):
    editions: list[WcEditionItem]


class WcHistoricalMatchItem(BaseModel):
    match_id: str
    season: int
    home_team: str
    away_team: str
    match_date: str
    phase: str
    phase_label: str
    group_name: str | None = None
    home_score: int
    away_score: int
    result: str
    result_label: str
    score: str


class WcEditionMatchesResponse(BaseModel):
    season: int
    matches: list[WcHistoricalMatchItem]


class WcValidateRequest(BaseModel):
    season: int = Field(..., ge=1930, le=2022)
    match_id: str | None = None
    home_team: str | None = None
    away_team: str | None = None


class WcValidateMatchInfo(BaseModel):
    match_id: str
    season: int
    home_team: str
    away_team: str
    match_date: str
    phase: str
    phase_label: str
    group_name: str | None = None
    home_score: int
    away_score: int
    actual_result: str
    actual_result_label: str
    actual_score: str


class NewsArticleItem(BaseModel):
    id: str
    source: str
    source_name: str
    source_url: str
    title: str
    summary: str | None = None
    body_preview: str
    published_at: str | None = None
    scraped_at: str | None = None
    teams_mentioned: list[str] = Field(default_factory=list)
    national_teams_mentioned: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    sentiment_score: float | None = None
    sentiment_label: str


class NewsSourceItem(BaseModel):
    id: str
    name: str
    count: int


class NewsFeedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    sources: list[NewsSourceItem]
    articles: list[NewsArticleItem]


class NewsCardsResponse(BaseModel):
    """Notícias formatadas para NewsArticleCard no frontend."""

    total: int
    limit: int
    offset: int
    teams: list[str] = Field(default_factory=list)
    cards: list[NewsArticleItem]


class NewsSyncResponse(BaseModel):
    collected: int
    by_source: dict[str, int]
    silver_updated: bool
    silver_path: str | None = None
    articles_silver: int
    synced_at: str


class WcValidateResponse(BaseModel):
    match: WcValidateMatchInfo
    prediction: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    poisson_score: str
    expected_goals: str
    correct: bool
    context: str
    h2h_summary: str
    model_breakdown: WcModelBreakdown
    cutoff_date: str
    cutoff_note: str


def _context_to_response(context, include_prediction: bool = False) -> MatchContextResponse:
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
    if include_prediction:
        pred, conf, reason = predict_baseline(context.features)
        resp.prediction = pred
        resp.confidence = conf
        resp.reason = reason
        resp.model_source = "baseline"
        resp.probabilities = predict_baseline_probs(context.features)
    return resp


def _breakdown_to_response(breakdown: dict) -> WcModelBreakdown:
    pf = breakdown.get("poisson_factors")
    return WcModelBreakdown(
        dixon_coles=breakdown["dixon_coles"],
        logistic=breakdown["logistic"],
        dixon_coles_rho=breakdown.get("dixon_coles_rho"),
        poisson_factors=WcGoalFactors(**pf) if pf else None,
        holdout_2022_accuracy=breakdown.get("holdout_2022_accuracy"),
        ensemble_weights=breakdown["ensemble_weights"],
        ensemble_brier=breakdown.get("ensemble_brier"),
        kxl_baseline=breakdown.get("kxl_baseline"),
        kxl_collision=breakdown.get("kxl_collision"),
        kxl_dynamic=breakdown.get("kxl_dynamic"),
    )


def _wc_prediction_to_response(pred: "WcPrediction") -> WcPredictionResponse:
    breakdown = pred.model_breakdown
    return WcPredictionResponse(
        home_team=pred.home_team,
        away_team=pred.away_team,
        prediction=pred.prediction,
        confidence=round(pred.confidence, 4),
        prob_home=round(pred.prob_home, 4),
        prob_draw=round(pred.prob_draw, 4),
        prob_away=round(pred.prob_away, 4),
        poisson_score=pred.poisson_score,
        expected_goals=pred.expected_goals,
        context=pred.context,
        h2h_summary=pred.h2h_summary,
        model_breakdown=_breakdown_to_response(breakdown),
    )


def _load_wc_round(path: Path = WC_ROUND_FILE) -> dict:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Rodada WC não encontrada: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler rodada WC: {exc}") from exc


def _match_value_to_response(report: MatchValueReport) -> WcMatchValueResponse:
    best = None
    if report.best:
        best = WcOutcomeValue(
            outcome=report.best.outcome,
            odd=report.best.odd,
            model_prob=report.best.model_prob,
            implied_prob=report.best.implied_prob,
            expected_value=report.best.expected_value,
            fair_odd=report.best.fair_odd,
            kelly_quarter=report.best.kelly_quarter,
        )
    outcomes = [
        WcOutcomeValue(
            outcome=item.outcome,
            odd=item.odd,
            model_prob=item.model_prob,
            implied_prob=item.implied_prob,
            expected_value=item.expected_value,
            fair_odd=item.fair_odd,
            kelly_quarter=item.kelly_quarter,
        )
        for item in report.outcomes
    ]
    return WcMatchValueResponse(
        home_team=report.home_team,
        away_team=report.away_team,
        best=best,
        outcomes=outcomes,
    )


def _sanitize_match_item(data: dict) -> dict:
    import math

    out = dict(data)
    group = out.get("group_name")
    if group is None or (isinstance(group, float) and math.isnan(group)):
        out["group_name"] = None
    else:
        out["group_name"] = str(group)
    return out


@app.get("/health/live")
def health_live():
    """Liveness para o proxy Fly — sem I/O no lake (sobe antes do warm de modelos)."""
    return {"status": "ok"}


@app.get("/health")
async def health():
    stats = collection_stats()
    articles_silver, fixtures = await asyncio.to_thread(get_lake_counts)
    return {
        "status": "ok",
        "lake_root": str(settings.lake_root),
        "articles_silver": articles_silver,
        "fixtures": fixtures,
        "collections": stats,
        "wc_models_ready": _wc_models_ready,
        "wc_artifact": _wc_artifact_meta if _wc_models_ready else None,
    }


@app.get("/data/pulse")
async def data_pulse():
    """Heartbeat do datalake (GET) — mesmo snapshot anexado via headers em cada requisição."""
    return await asyncio.to_thread(
        build_pulse_snapshot,
        wc_models_ready=_wc_models_ready,
        force_lake_counts=True,
    )


@app.get("/")
def root():
    return {
        "name": "api-noticia",
        "status": "running",
        "auth_required": api_key_enabled(),
        "docs": "/docs",
        "health": "/health",
        "data_pulse": "/data/pulse",
        "endpoints": [
            "/data/pulse",
            "/news/feed",
            "/news/cards",
            "/news/all",
            "/news/sync",
            "/context",
            "/predict",
            "/round/predict",
            "/worldcup/predict",
            "/worldcup/round",
            "/worldcup/schedule",
            "/worldcup/squads",
            "/worldcup/squads/{team}",
            "/worldcup/teams",
            "/worldcup/value/live",
            "/worldcup/editions",
            "/worldcup/editions/{season}/matches",
            "/worldcup/validate",
            "/worldcup/walkforward",
            "/worldcup/retrain",
            "/worldcup/group-standings",
        ],
    }


@app.post("/news/sync", response_model=NewsSyncResponse)
async def news_sync(
    full_rebuild: bool = Query(
        False,
        description="Reprocessa todo o bronze no silver (use após purge-news)",
    ),
    fetch_body: bool | None = Query(
        None,
        description="Baixa o HTML de cada URL (texto completo no body_preview; bem mais lento)",
    ),
):
    try:
        do_fetch = (
            settings.news_sync_fetch_body if fetch_body is None else fetch_body
        )
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


@app.get("/news/feed", response_model=NewsFeedResponse)
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
        build_news_feed,
        silver_df,
        limit=limit,
        offset=offset,
        source=source,
        query=q,
        days=days,
    )
    return NewsFeedResponse(
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
        sources=[NewsSourceItem(**s) for s in payload["sources"]],
        articles=[NewsArticleItem(**a) for a in payload["articles"]],
    )


@app.get("/news/all", response_model=NewsFeedResponse)
async def news_all(
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
    days: int | None = Query(
        None,
        description="Janela em dias; omita para trazer todo o histórico no lake",
    ),
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
        build_news_all,
        silver_df,
        offset=offset,
        source=source,
        query=q,
        days=days,
        teams=resolved_teams,
    )
    return NewsFeedResponse(
        total=payload["total"],
        limit=len(payload["articles"]),
        offset=payload["offset"],
        sources=[NewsSourceItem(**s) for s in payload["sources"]],
        articles=[NewsArticleItem(**a) for a in payload["articles"]],
    )


@app.get("/news/cards", response_model=NewsCardsResponse)
async def news_cards(
    limit: int = 12,
    offset: int = 0,
    source: str | None = None,
    q: str | None = None,
    days: int | None = 14,
    team: str | None = Query(None, description="Filtrar por um time/seleção"),
    home_team: str | None = Query(None, description="Mandante (usa com away_team)"),
    away_team: str | None = Query(None, description="Visitante"),
    teams: str | None = Query(
        None,
        description="Lista separada por vírgula, ex: Brasil,Marrocos",
    ),
):
    limit = min(max(limit, 1), 48)
    offset = max(offset, 0)
    if days is not None:
        days = min(max(days, 1), 90)

    team_list: list[str] | None = None
    if teams:
        team_list = [t.strip() for t in teams.split(",") if t.strip()]

    home = normalize_national_team(home_team) if home_team else None
    away = normalize_national_team(away_team) if away_team else None
    single = normalize_national_team(team) if team else None

    silver_df = await asyncio.to_thread(load_silver)
    payload = await asyncio.to_thread(
        build_news_cards,
        silver_df,
        limit=limit,
        offset=offset,
        source=source,
        query=q,
        days=days,
        team=single,
        home_team=home,
        away_team=away,
        teams=team_list,
    )
    return NewsCardsResponse(
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
        teams=payload["teams"],
        cards=[NewsArticleItem(**c) for c in payload["cards"]],
    )


@app.post("/context", response_model=MatchContextResponse)
def get_match_context(req: MatchRequest):
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
    return _context_to_response(context)


@app.post("/predict", response_model=MatchContextResponse)
def predict_match(req: MatchRequest):
    resp = get_match_context(req)
    context = build_gold_for_match(
        match_id=resp.match_id,
        home_team=resp.home_team,
        away_team=resp.away_team,
        round_number=req.round_number,
        competition=req.competition,
        match_date=datetime.now(timezone.utc),
        silver_df=load_silver(),
        season=req.season,
        fixtures_df=load_fixtures(),
        live_mode=True,
    )
    pred, conf, reason = predict_baseline(context.features)
    resp.prediction = pred
    resp.confidence = conf
    resp.reason = reason
    resp.model_source = "baseline"
    resp.probabilities = predict_baseline_probs(context.features)
    return resp


@app.get("/round/predict", response_model=RoundResponse)
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


@app.post("/worldcup/predict", response_model=WcPredictionResponse)
def worldcup_predict(req: WcPredictRequest):
    try:
        predictor = _get_wc_predictor()
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
        pred = predictor.predict(
            home,
            away,
            phase=req.phase,
            kxl_match=req.kxl_match,
            season=2026,
            group_name=lookup_2026_group(home, away) if req.phase == "group" else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _wc_prediction_to_response(pred)


def _build_wc_round_predictions(
    predictor: "WcPredictor",
    round_data: dict,
    *,
    matchday: int | None = None,
) -> list[WcPredictionResponse]:
    cache = _wc_round_cache()
    phase_default = round_data.get("phase", "group")
    matches = round_data.get("matches", [])
    if matchday is not None:
        matches = [m for m in matches if m.get("round") == matchday]

    predictions: list[WcPredictionResponse] = []
    dirty = False

    for match in matches:
        home = normalize_national_team(match["home_team"])
        away = normalize_national_team(match["away_team"])
        match_phase = match.get("phase", phase_default)
        key = cache.match_key(home, away, match_phase)

        cached = cache.get_cached(key)
        if cached is not None:
            predictions.append(WcPredictionResponse(**cached))
            continue

        try:
            pred = predictor.predict(
                home,
                away,
                phase=match_phase,
                season=round_data.get("season", 2026),
                group_name=match.get("group"),
            )
            resp = _wc_prediction_to_response(pred)
            cache.set_cached(key, resp.model_dump())
            predictions.append(resp)
            dirty = True
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Erro ao prever {home} x {away}: {exc}",
            ) from exc

    if dirty:
        cache.persist_to_disk()

    return predictions


@app.get("/worldcup/round", response_model=WcRoundResponse)
def worldcup_round(
    matchday: int | None = Query(None, alias="round", ge=1, le=3),
):
    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    round_data = _load_wc_round()
    phase_default = round_data.get("phase", "group")
    predictions = _build_wc_round_predictions(
        predictor,
        round_data,
        matchday=matchday,
    )

    return WcRoundResponse(
        season=round_data.get("season", 2026),
        competition=round_data.get("competition", "Copa do Mundo"),
        phase=phase_default,
        round=matchday if matchday is not None else round_data.get("round", 0),
        predictions=predictions,
    )


@app.get("/worldcup/group-standings", response_model=WcGroupStandingsResponse)
def worldcup_group_standings():
    try:
        predictor = _get_wc_predictor()
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

    pred_rows: list[dict] = []
    for pred in predictions:
        key = (pred.home_team, pred.away_team)
        pred_rows.append(
            {
                "home_team": pred.home_team,
                "away_team": pred.away_team,
                "prediction": pred.prediction,
                "group": pair_group.get(key),
            }
        )

    groups_meta = round_data.get("groups", [])
    blocks = build_group_standings(groups_meta, pred_rows)
    return WcGroupStandingsResponse(
        season=int(round_data.get("season", 2026)),
        competition=round_data.get("competition", "Copa do Mundo FIFA 2026"),
        simulated=True,
        note="Pontos simulados pelos palpites do modelo (3 vitória, 1 empate, 0 derrota).",
        groups=[WcGroupStandingsBlock(**block) for block in blocks],
    )


@app.get("/worldcup/teams", response_model=WcTeamsResponse)
def worldcup_teams():
    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    fixtures = predictor.fixtures
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


@app.get("/worldcup/schedule", response_model=WcScheduleResponse)
def worldcup_schedule():
    try:
        data = load_wc_schedule()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Calendário WC inválido: {exc}") from exc

    payload = build_schedule_response(data)
    return WcScheduleResponse(**payload)


@app.get("/worldcup/squads", response_model=WcSquadTeamsResponse)
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


@app.get("/worldcup/squads/{team}", response_model=WcSquadDetailResponse)
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


@app.get("/worldcup/editions", response_model=WcEditionsResponse)
def worldcup_editions():
    from pipelines.wc_validate import list_wc_editions

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    editions = list_wc_editions(predictor.fixtures)
    return WcEditionsResponse(
        editions=[WcEditionItem(**e) for e in editions],
    )


@app.get("/worldcup/editions/{season}/matches", response_model=WcEditionMatchesResponse)
def worldcup_edition_matches(season: int):
    from pipelines.wc_validate import list_edition_matches

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    matches = list_edition_matches(predictor.fixtures, season)
    if not matches:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum jogo encontrado para a edição {season}",
        )
    return WcEditionMatchesResponse(
        season=season,
        matches=[WcHistoricalMatchItem(**_sanitize_match_item(m)) for m in matches],
    )


@app.post("/worldcup/validate", response_model=WcValidateResponse)
def worldcup_validate(req: WcValidateRequest):
    if not req.match_id and (not req.home_team or not req.away_team):
        raise HTTPException(
            status_code=400,
            detail="Informe match_id ou home_team e away_team",
        )

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home = normalize_national_team(req.home_team) if req.home_team else None
    away = normalize_national_team(req.away_team) if req.away_team else None

    from pipelines.wc_validate import validate_historical_match

    try:
        result = validate_historical_match(
            predictor,
            predictor.fixtures,
            req.season,
            match_id=req.match_id,
            home_team=home,
            away_team=away,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    breakdown = result["model_breakdown"]
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
        model_breakdown=_breakdown_to_response(breakdown),
        cutoff_date=result["cutoff_date"],
        cutoff_note=result["cutoff_note"],
    )


@app.get("/worldcup/walkforward")
def worldcup_walkforward():
    report_path = settings.lake_root / "reports" / "wc_walkforward_report.json"
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Relatório ausente. Execute: walkforward-wc-models",
        )
    return json.loads(report_path.read_text(encoding="utf-8"))


@app.post("/worldcup/retrain")
def worldcup_retrain():
    global _wc_predictor, _wc_artifact_meta, _wc_models_ready
    try:
        from models.wc_artifact import load_or_train_wc_predictor

        _wc_predictor, _wc_artifact_meta = load_or_train_wc_predictor(force=True)
        _wc_models_ready = True
        _wc_round_cache().invalidate_wc_round_cache()
    except ValueError as exc:
        _wc_models_ready = False
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "status": "ok",
        "artifact": _wc_artifact_meta,
    }


@app.post("/worldcup/value/live", response_model=WcValueResponse)
def worldcup_live_value(req: WcValueRequest):
    schedule_path = Path(req.schedule_file)
    if not schedule_path.exists():
        raise HTTPException(status_code=404, detail=f"Schedule não encontrado: {schedule_path}")

    try:
        schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao ler schedule: {exc}") from exc

    try:
        live_odds = fetch_live_h2h_odds(
            sport_key=req.sport_key,
            regions=req.regions,
            preferred_bookmaker=req.bookmaker,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao consultar Odds API: {exc}") from exc

    merged, matched = merge_schedule_with_odds(schedule, live_odds)
    if req.save_odds_file:
        save_odds_file(merged, Path(req.output_odds_file))

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    phase_default = merged.get("phase", "group")
    reports: list[WcMatchValueResponse] = []

    for match in merged.get("matches", []):
        phase = match.get("phase", phase_default)
        pred = predictor.predict(match["home_team"], match["away_team"], phase=phase)
        probabilities = {"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away}
        value = evaluate_match(
            home_team=match["home_team"],
            away_team=match["away_team"],
            probabilities=probabilities,
            odds=match["odds"],
            min_edge=req.min_edge,
        )
        reports.append(_match_value_to_response(value))

    return WcValueResponse(
        matched_games=matched,
        total_schedule_games=len(schedule.get("matches", [])),
        source=merged.get("source", "the-odds-api"),
        captured_at=merged.get("captured_at"),
        edges=reports,
    )
