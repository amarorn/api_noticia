import asyncio
import json
import threading
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
from models.corners_predictor import CornersPredictor
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
from pipelines.wc_group_standings import (
    build_group_standings,
    build_group_standings_from_results,
    load_wc_group_results,
    merge_real_into_simulated,
)
from schemas.national_teams import normalize_national_team
from schemas.user_bet import CheckAgainstModelRequest, SettledBetsBatchRequest, UserOpenBetRequest

WC_ROUND_FILE = Path("data/rounds/wc_2026.json")

_wc_models_ready = False
_wc_predictor: Any = None
_wc_artifact_meta: dict = {}
_wc_train_lock = threading.Lock()
_wc_train_thread: threading.Thread | None = None


def _wc_round_cache():
    from api import wc_round_cache

    return wc_round_cache


def _warm_sofascore_imports() -> None:
    """Carrega módulos Sofascore no thread principal (evita deadlock no thread pool)."""
    try:
        import ingest.sofascore.client  # noqa: F401
        import ingest.sofascore.fept_ingest  # noqa: F401
        import ingest.sofascore.stats_ingest  # noqa: F401
    except ImportError:
        pass


def _warm_wc_models() -> None:
    global _wc_models_ready
    _warm_sofascore_imports()
    try:
        CornersPredictor()
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
            force=force or settings.wc_artifact_force_retrain,
            allow_train=force or settings.wc_artifact_force_retrain,
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


class WcCornersPredictRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Marrocos"])
    phase: str = Field("group", examples=["group"])


class WcCornerFactors(BaseModel):
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
    training_matches: int
    blend_with_goal_proxy: float


class WcCornersPredictResponse(BaseModel):
    home_team: str
    away_team: str
    data_source: str
    expected_corners: str
    expected_total_corners: float
    most_likely_corners: str
    prob_home_more_corners: float
    prob_draw_corners: float
    prob_away_more_corners: float
    line_probs: dict[str, float]
    factors: WcCornerFactors
    training_summary: dict


class WcPredictRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Marrocos"])
    phase: str = Field("group", examples=["group"])
    match_date: str | None = Field(
        None,
        description="Data do confronto (ISO); usada em /simulate e busca Sofascore",
        examples=["2026-06-06"],
    )
    fifa_match_id: str | None = Field(
        None,
        description="IdMatch FIFA; evita busca na janela quando conhecido",
        examples=["400123456"],
    )
    sofascore_event_id: int | None = Field(
        None,
        description="ID do evento Sofascore; preenche FEPT automaticamente se kxl_match.fept ausente",
        examples=[11774480],
    )
    kxl_match: WcKxlMatchInput | None = Field(
        None,
        description="Entrada dinâmica KXL (FECL, FEJU, FEDE, FEPT, FEEM) — opcional",
    )


class WcInPlayRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Egito"])
    home_score: int = Field(..., ge=0, examples=[1])
    away_score: int = Field(..., ge=0, examples=[1])
    minute: int = Field(..., ge=0, le=120, description="Minuto de jogo (0–120)", examples=[17])
    phase: str = Field("group", examples=["group"])
    match_minutes: int = Field(90, ge=45, le=120, examples=[90])
    ht_home_score: int | None = Field(
        None,
        ge=0,
        description="Placar no intervalo (casa). Recomendado quando minute > 45.",
    )
    ht_away_score: int | None = Field(
        None,
        ge=0,
        description="Placar no intervalo (fora). Recomendado quando minute > 45.",
    )
    superbet_event_id: int | None = Field(
        None,
        description="ID Superbet: preenche placar/minuto ao vivo e benchmark de mercado",
        examples=[13247229],
    )
    merge_superbet_odds: bool = Field(
        False,
        description="Salva snapshot nas odds de mercado (superbet_odds.json) para treino",
    )


class WcInPlayResponse(BaseModel):
    home_team: str
    away_team: str
    current_score: str
    minute: int
    match_minutes: int
    remaining_fraction: float
    lambda_full_home: float
    lambda_full_away: float
    lambda_remaining_home: float
    lambda_remaining_away: float
    rho_used: float
    prob_final_home: float
    prob_final_draw: float
    prob_final_away: float
    prob_ht_home: float
    prob_ht_draw: float
    prob_ht_away: float
    prob_no_more_goals: float
    prob_next_goal_home: float
    prob_next_goal_away: float
    final_line_probs: dict[str, float]
    remainder_line_probs: dict[str, float]
    ht_line_probs: dict[str, float]
    second_half_line_probs: dict[str, float]
    team_final_line_probs: dict[str, float]
    top_final_scores: dict[str, float]
    top_ht_ft: dict[str, float]
    combo_markets: dict[str, float]
    btts_final: float
    handicap_probs: dict[str, float] = Field(default_factory=dict)
    n_simulations: int
    market_benchmark: dict | None = None
    superbet: dict | None = None


class UserBetRequest(BaseModel):
    market: str = Field(..., examples=["h2h"], description="h2h, over_2_5, btts, next_goal, combo_btts_over_3_5")
    outcome: str = Field(..., examples=["1"], description="1, X, 2, yes, no, home, away")
    stake: float = Field(..., gt=0, examples=[100])
    odds_placed: float = Field(..., gt=1, examples=[2.1])


class WcBetAdviceRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Egito"])
    superbet_event_id: int = Field(..., examples=[13247229])
    phase: str = Field("friendly", examples=["friendly"])
    bankroll: float = Field(1000, gt=0, examples=[1000])
    user_bet: UserBetRequest | None = None


class WcBetAdviceResponse(BaseModel):
    home_team: str
    away_team: str
    minute: int
    current_score: str | None
    cashout: dict | None
    aportes: list[dict]
    inplay_summary: dict
    superbet_event_id: int
    confidence: dict | None = None


class WcSuperbetLiveAdviceResponse(WcBetAdviceResponse):
    period_label: str | None = None
    status: str | None = None
    is_finished: bool = False
    is_live: bool = True
    superbet_stale: bool = False
    superbet_error: str | None = None
    h2h_odds: dict[str, float] = Field(default_factory=dict)
    h2h_implied: dict[str, float] = Field(default_factory=dict)
    h2h_overround: float | None = None
    generosity_probs: dict[str, float] = Field(default_factory=dict)
    market_benchmark: dict | None = None
    strategy: dict | None = None
    captured_at: str | None = None
    betradar_id: str | None = None
    raw_market_count: int = 0
    btts_odds: dict[str, float] = Field(default_factory=dict)
    next_goal_odds: dict[str, float] = Field(default_factory=dict)
    analysis_coverage: dict[str, bool | list[str]] | None = None
    hedge_report: dict | None = None
    against_model_alerts: list[dict] = Field(default_factory=list)
    trend_report: dict | None = None
    live_stats: dict | None = None
    halftime_report: dict | None = None
    half_tickets: dict | None = None
    viable_2h_markets: dict | None = None


class HandicapLineResponse(BaseModel):
    line: float
    side: str
    model_prob: float
    superbet_odd: float | None = None
    ev: float | None = None
    kelly_stake: float = 0.0
    recommendation: str


class HandicapAnalysisResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    current_score: str
    minute: int
    phase: str
    lines: list[HandicapLineResponse]
    best_bet: HandicapLineResponse | None = None
    model_probs: dict[str, float] = Field(default_factory=dict)
    superbet_odds: dict[str, float] = Field(default_factory=dict)
    timestamp: str


class WcSuperbetLiveEventResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    sport_id: int
    tournament_id: int | None
    utc_date: str | None
    betradar_id: str | None
    minute: int
    home_score: int
    away_score: int
    period_label: str | None
    status: str | None
    market_count: int
    h2h_odds: dict[str, float]
    captured_at: str
    bet_rank_score: float | None = None
    bet_tier: str | None = None
    bet_label: str | None = None
    bet_palpite: str | None = None
    bet_opportunity_count: int | None = None
    bet_top_ev: float | None = None
    bet_top_label: str | None = None


class WcSuperbetLiveResponse(BaseModel):
    count: int
    sport_id: int | None
    events: list[WcSuperbetLiveEventResponse]
    captured_at: str


class WcSuperbetEventResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    utc_date: str | None
    betradar_id: str | None
    is_live: bool
    inplay: dict | None
    h2h_odds: dict[str, float]
    h2h_implied: dict[str, float]
    totals_implied: dict[str, dict[str, float]]
    corners_implied: dict[str, dict[str, float]]
    combo_markets: dict[str, dict[str, float]]
    generosity_probs: dict[str, float]
    raw_market_count: int
    captured_at: str
    superbet_stale: bool = False


class BetBuilderLegInput(BaseModel):
    market: str = ""
    outcome: str = "yes"
    label: str | None = None


class BetBuilderValidateRequest(BaseModel):
    legs: list[BetBuilderLegInput] = Field(..., min_length=1)
    minute: int | None = Field(None, ge=0, le=120)
    home_score: int = Field(0, ge=0)
    away_score: int = Field(0, ge=0)
    ht_home_score: int | None = Field(None, ge=0)
    ht_away_score: int | None = Field(None, ge=0)
    combined_odd: float | None = Field(None, gt=1)


class BetBuilderValidateResponse(BaseModel):
    valid: bool
    errors: list[dict] = Field(default_factory=list)
    warnings: list[dict] = Field(default_factory=list)
    legs_count: int
    bet_builder_rules: list[str] = Field(default_factory=list)


class WcSuperbetPostmortemTipSummary(BaseModel):
    total_ticks_with_tip: int
    unique_tips: int | None = None
    won: int
    lost: int
    unknown: int


class WcSuperbetPostmortemResponse(BaseModel):
    event_id: int
    home_team: str | None = None
    away_team: str | None = None
    final_score: str
    ht_score: str | None = None
    n_ticks: int
    kickoff_probs: dict[str, float] | None = None
    final_probs: dict[str, float] | None = None
    tip_summary: WcSuperbetPostmortemTipSummary
    tips_by_market: list[dict[str, Any]]
    model_timeline: list[dict[str, Any]]
    issues: list[dict[str, str]]


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


class WcMonteCarloBreakdown(BaseModel):
    prob_home: float
    prob_draw: float
    prob_away: float
    expected_goals_home: float
    expected_goals_away: float
    over_2_5: float
    under_2_5: float
    both_teams_score: float
    clean_sheet_home: float
    clean_sheet_away: float
    top_scores: dict[str, float]
    n_simulations: int
    rho_used: float


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
    kxl_fept: dict | None = None
    monte_carlo: WcMonteCarloBreakdown | None = None


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
    max_prob_outcome: str | None = None
    max_prob: float | None = None
    prob_margin: float | None = None
    uncertainty: str | None = None
    pick_reason: str | None = None
    actual_score: str | None = None
    actual_outcome: str | None = None
    prediction_hit: bool | None = None


class WcSimulationScore(BaseModel):
    score: str
    prob: float


class WcSimulationScenario(BaseModel):
    name: str
    description: str
    prob: float


class WcSimulationResponse(BaseModel):
    home_team: str
    away_team: str
    match_date: str | None
    prediction: str
    confidence: float
    prob_home: float
    prob_draw: float
    prob_away: float
    poisson_score: str | None = None
    expected_goals: str | None = None

    # Dados reais da FIFA
    fifa_home_lineup: list[dict[str, Any]] | None = None
    fifa_away_lineup: list[dict[str, Any]] | None = None
    fifa_home_bench: list[dict[str, Any]] | None = None
    fifa_away_bench: list[dict[str, Any]] | None = None
    fifa_home_goals: list[dict[str, Any]] | None = None
    fifa_away_goals: list[dict[str, Any]] | None = None
    fifa_home_tactics: str | None = None
    fifa_away_tactics: str | None = None
    fifa_home_coach: str | None = None
    fifa_away_coach: str | None = None
    fifa_stadium: str | None = None
    fifa_attendance: int | None = None
    fifa_home_points: float | None = None
    fifa_away_points: float | None = None
    fifa_points_diff: float | None = None
    lineup_source: str | None = Field(
        None,
        description="Origem das escalações exibidas: fifa ou sofascore",
    )

    # Dados enriquecidos
    enrich_features: dict[str, Any] | None = None
    stats_features: dict[str, Any] | None = None
    model_breakdown: dict[str, Any]
    warnings: list[str]


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
    real_points: int = 0
    real_played: int = 0
    real_gd: int = 0


class WcGroupStandingsBlock(BaseModel):
    group: str
    standings: list[WcGroupStandingRow]


class WcGroupStandingsResponse(BaseModel):
    season: int
    competition: str
    simulated: bool = True
    note: str
    as_of: str
    n_real_results: int = 0
    groups: list[WcGroupStandingsBlock]


class WcTeamsResponse(BaseModel):
    teams: list[str]
    count: int


class WcFriendlyItem(BaseModel):
    event_id: int | None = None
    fifa_match_id: str | None = None
    sources: list[str] = Field(default_factory=lambda: ["sofascore"])
    home_team: str
    away_team: str
    match_date: str | None = None
    status: str
    home_score: int | None = None
    away_score: int | None = None
    tournament: str
    is_home: bool


class WcFriendliesResponse(BaseModel):
    team: str
    year: int
    count: int
    friendlies: list[WcFriendlyItem]
    source: str = "sofascore+fifa"


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
    mc = breakdown.get("monte_carlo")
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
        kxl_fept=breakdown.get("kxl_fept"),
        monte_carlo=WcMonteCarloBreakdown(**mc) if mc else None,
    )


def _wc_prediction_to_response(
    pred: "WcPrediction",
    *,
    actual_score: str | None = None,
    actual_outcome: str | None = None,
) -> WcPredictionResponse:
    from models.wc_prediction_meta import build_prediction_metadata

    breakdown = pred.model_breakdown
    meta = build_prediction_metadata(
        {"1": pred.prob_home, "X": pred.prob_draw, "2": pred.prob_away},
        pred.prediction,
    )
    prediction_hit = None
    if actual_outcome is not None:
        prediction_hit = pred.prediction == actual_outcome

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
        max_prob_outcome=meta["max_prob_outcome"],
        max_prob=meta["max_prob"],
        prob_margin=meta["prob_margin"],
        uncertainty=meta["uncertainty"],
        pick_reason=meta["pick_reason"],
        actual_score=actual_score,
        actual_outcome=actual_outcome,
        prediction_hit=prediction_hit,
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


@app.get("/config/sportradar")
def config_sportradar():
    """Config pública do widget LMT (client id omitido se ausente)."""
    from api.sportradar_embed import sportradar_public_config

    payload = sportradar_public_config()
    return {
        "widget": payload["widget"],
        "language": payload["language"],
        "embed_available": payload["embed_available"],
        "client_id_configured": payload["client_id"] is not None,
    }


@app.get("/sportradar/lmt/{betradar_id}", response_class=HTMLResponse)
def sportradar_lmt_embed(betradar_id: str):
    """Página iframe com match.lmtPlus — feed Sportradar em tempo real via betradar_id."""
    from api.sportradar_embed import lmt_embed_response

    return lmt_embed_response(betradar_id=betradar_id)


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
            "/worldcup/inplay",
            "/worldcup/superbet/live",
            "/worldcup/superbet/live/{event_id}/advice",
            "/worldcup/superbet/events/{event_id}",
            "/worldcup/superbet/events/{event_id}/postmortem",
            "/worldcup/handicap/{event_id}",
            "/worldcup/bet/advice",
            "/worldcup/round",
            "/worldcup/schedule",
            "/worldcup/squads",
            "/worldcup/squads/{team}",
            "/worldcup/teams",
            "/worldcup/friendlies",
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


class WcSofascoreResolveResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    match_date: str
    sofascore_home: str | None = None
    sofascore_away: str | None = None


class WcSofascoreStatsResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    match_date: str | None = None
    stats: dict[str, float | int | str | None]
    fetched_at: str
    source: str = "sofascore"
    cached: bool = False


@app.get("/worldcup/sofascore/resolve", response_model=WcSofascoreResolveResponse)
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
        client = SofascoreClient()
        event = find_event_id(
            client,
            home_team=home,
            away_team=away,
            match_date=match_date,
        )
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


@app.get(
    "/worldcup/sofascore/{event_id}/statistics",
    response_model=WcSofascoreStatsResponse,
)
def worldcup_sofascore_statistics(
    event_id: int,
    refresh: bool = Query(False, description="Força nova coleta no Sofascore"),
):
    from datetime import datetime, timezone

    from api.sofascore_http import ensure_sofascore_not_in_cooldown, raise_sofascore_http_error
    from ingest.sofascore.stats_ingest import ingest_match_stats, load_match_stats

    if not refresh:
        cached = load_match_stats(event_id)
        if cached:
            fetched_at = cached.get("fetched_at")
            if not isinstance(fetched_at, str):
                fetched_at = datetime.now(timezone.utc).isoformat()
            stats = {
                k: v
                for k, v in cached.items()
                if k
                not in (
                    "event_id",
                    "home_team",
                    "away_team",
                    "match_date",
                    "source",
                    "fetched_at",
                )
            }
            return WcSofascoreStatsResponse(
                event_id=int(cached["event_id"]),
                home_team=str(cached["home_team"]),
                away_team=str(cached["away_team"]),
                match_date=cached.get("match_date"),
                stats=stats,
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
    stats = {
        k: v
        for k, v in payload.items()
        if k
        not in (
            "event_id",
            "home_team",
            "away_team",
            "match_date",
            "source",
            "fetched_at",
        )
    }
    return WcSofascoreStatsResponse(
        event_id=result.event_id,
        home_team=result.home_team,
        away_team=result.away_team,
        match_date=result.match_date,
        stats=stats,
        fetched_at=str(payload["fetched_at"]),
        cached=False,
    )


@app.post("/worldcup/corners/predict", response_model=WcCornersPredictResponse)
def worldcup_corners_predict(req: WcCornersPredictRequest):
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


@app.get("/worldcup/superbet/live", response_model=WcSuperbetLiveResponse)
def worldcup_superbet_live(
    sport_id: int = Query(5, description="Filtra por esporte (5=futebol)."),
    all_sports: bool = Query(False, description="Ignora sport_id e retorna todos os esportes."),
    rank: bool = Query(True, description="Ordena e enriquece com score de palpite in-play."),
):
    """Lista jogos ao vivo na Superbet (feed /live)."""
    from datetime import datetime, timezone

    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.live_rank import rank_live_events

    filter_sport = None if all_sports else sport_id
    try:
        events = SuperbetClient().fetch_live_events(sport_id=filter_sport)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    captured_at = datetime.now(timezone.utc).isoformat()
    if rank:
        ranked = rank_live_events(events)
        payload = [
            WcSuperbetLiveEventResponse(**{**event.to_dict(), **bet_rank.to_dict()})
            for event, bet_rank in ranked
        ]
    else:
        payload = [WcSuperbetLiveEventResponse(**event.to_dict()) for event in events]

    return WcSuperbetLiveResponse(
        count=len(payload),
        sport_id=filter_sport,
        events=payload,
        captured_at=captured_at,
    )


@app.get("/worldcup/superbet/live/{event_id}/advice", response_model=WcSuperbetLiveAdviceResponse)
async def worldcup_superbet_live_advice(
    event_id: int,
    phase: str = Query("friendly", description="Fase do modelo (friendly para amistosos)"),
    bankroll: float = Query(1000, gt=0),
    market: str | None = Query(None, description="Mercado da aposta ativa (h2h, over_2_5, btts, next_goal)"),
    outcome: str | None = Query(None, description="Palpite da aposta (1, X, 2, yes, home, away)"),
    stake: float | None = Query(None, gt=0),
    odds_placed: float | None = Query(None, gt=1),
    fast: bool = Query(
        False,
        description="Resposta rápida: pula Sofascore ao vivo e gravação bronze/tick (overlay/extensão).",
    ),
    kickoff: str | None = Query(
        None,
        description="Kickoff ISO do jogo (recalibra features do modelo até o apito)",
    ),
):
    """Captura evento Superbet ao vivo, roda modelo e retorna cash-out / aportes."""
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_bet_advice import UserBetInput

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_bet = None
    if market and outcome and stake is not None and odds_placed is not None:
        user_bet = UserBetInput(
            market=market,
            outcome=outcome,
            stake=stake,
            odds_placed=odds_placed,
        )

    try:
        payload = await asyncio.to_thread(
            run_live_advice,
            event_id,
            predictor,
            phase=phase,
            bankroll=bankroll,
            user_bet=user_bet,
            save_bronze=not fast,
            save_tick=not fast,
            use_sofascore_live=False if fast else None,
            fast=fast,
            kickoff=kickoff,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WcSuperbetLiveAdviceResponse(**payload)


@app.get("/worldcup/superbet/events/{event_id}", response_model=WcSuperbetEventResponse)
async def worldcup_superbet_event(
    event_id: int,
    merge_odds: bool = False,
    save_bronze: bool = True,
):
    """Snapshot Superbet: estado ao vivo, odds e probabilidades implícitas."""
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import fetch_event_with_stale_fallback, merge_snapshot_into_odds_file, save_event_snapshot

    client = SuperbetClient()
    try:
        snapshot, superbet_stale = await asyncio.to_thread(
            fetch_event_with_stale_fallback, client, event_id
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if save_bronze and not superbet_stale:
        await asyncio.to_thread(save_event_snapshot, snapshot)
    if merge_odds and snapshot.h2h_odds:
        await asyncio.to_thread(merge_snapshot_into_odds_file, snapshot)
        from pipelines.wc_market_features import load_match_odds_index

        load_match_odds_index.cache_clear()

    payload = snapshot.to_dict()
    payload["superbet_stale"] = superbet_stale
    return WcSuperbetEventResponse(**payload)


@app.post("/worldcup/superbet/validate-builder", response_model=BetBuilderValidateResponse)
def worldcup_superbet_validate_builder(req: BetBuilderValidateRequest):
    """Valida pernas do Criar Aposta antes de montar na Superbet."""
    from models.inplay_bet_builder_guard import validate_bet_builder

    legs = [leg.model_dump() for leg in req.legs]
    result = validate_bet_builder(
        legs,
        minute=req.minute,
        home_score=req.home_score,
        away_score=req.away_score,
        ht_home=req.ht_home_score,
        ht_away=req.ht_away_score,
        combined_odd=req.combined_odd,
    )
    return BetBuilderValidateResponse(**result)


@app.get(
    "/worldcup/superbet/events/{event_id}/postmortem",
    response_model=WcSuperbetPostmortemResponse,
)
async def worldcup_superbet_event_postmortem(
    event_id: int,
    regenerate: bool = Query(
        False,
        description="Regera post-mortem a partir de final.json e live_ticks",
    ),
):
    """Relatório pós-jogo: liquidação de tips, timeline do modelo e issues."""
    from pipelines.inplay_postmortem import get_or_build_inplay_postmortem

    report = await asyncio.to_thread(
        get_or_build_inplay_postmortem,
        event_id,
        regenerate=regenerate,
    )
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Post-mortem não encontrado para evento {event_id}",
        )
    return WcSuperbetPostmortemResponse(**report)


@app.get("/worldcup/combo-ticket")
async def worldcup_combo_ticket(
    home_team: str = Query(..., description="Seleção mandante"),
    away_team: str = Query(..., description="Seleção visitante"),
    bankroll: float = Query(1000, gt=0),
    superbet_event_id: int | None = Query(
        None,
        description="Opcional: cruza odds/EV com snapshot Superbet deste evento",
    ),
):
    """Monta bilhete combo KXL (padrões 9/10–10/10) com odds Superbet opcionais."""
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from models.wc_team_patterns import build_combo_ticket

    snapshot = None
    if superbet_event_id is not None:
        try:
            snapshot = await asyncio.to_thread(SuperbetClient().fetch_event, superbet_event_id)
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return build_combo_ticket(
        home_team,
        away_team,
        bankroll=bankroll,
        snapshot=snapshot,
    )


@app.get("/worldcup/handicap/{event_id}", response_model=HandicapAnalysisResponse)
def worldcup_handicap_analysis(
    event_id: int,
    bankroll: float = Query(default=1000.0, ge=10.0),
    phase: str = Query(default="group"),
):
    """Análise de handicap asiático: probabilidades modelo × odds Superbet."""
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import fetch_event_with_stale_fallback, save_event_snapshot
    from models.wc_handicap_analysis import build_handicap_analysis
    from models.wc_inplay import inplay_from_predictor

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        snapshot, _stale = fetch_event_with_stale_fallback(SuperbetClient(), event_id)
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    save_event_snapshot(snapshot)
    home = normalize_national_team(snapshot.home_team)
    away = normalize_national_team(snapshot.away_team)

    if snapshot.inplay:
        ip = snapshot.inplay
        home_score, away_score, minute = ip.home_score, ip.away_score, ip.minute
        ht_h, ht_a = ip.ht_home_score, ip.ht_away_score
    else:
        home_score = away_score = minute = 0
        ht_h = ht_a = None

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
    payload = build_handicap_analysis(
        event_id=event_id,
        home_team=home,
        away_team=away,
        current_score=f"{home_score}x{away_score}",
        minute=minute,
        model_probs=result.handicap_probs,
        snapshot=snapshot,
        bankroll=bankroll,
        phase=phase,
    )
    return HandicapAnalysisResponse(**payload)


@app.post("/worldcup/bet/advice", response_model=WcBetAdviceResponse)
def worldcup_bet_advice(req: WcBetAdviceRequest):
    """Captura jogo ao vivo (Superbet), roda modelo e recomenda cash-out / aporte."""
    from ingest.superbet.advice import run_live_advice
    from ingest.superbet.client import SuperbetClientError
    from models.wc_bet_advice import UserBetInput

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user_bet = None
    if req.user_bet is not None:
        user_bet = UserBetInput(
            market=req.user_bet.market,
            outcome=req.user_bet.outcome,
            stake=req.user_bet.stake,
            odds_placed=req.user_bet.odds_placed,
        )

    try:
        payload = run_live_advice(
            req.superbet_event_id,
            predictor,
            phase=req.phase,
            bankroll=req.bankroll,
            user_bet=user_bet,
        )
    except SuperbetClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WcBetAdviceResponse(
        home_team=payload["home_team"],
        away_team=payload["away_team"],
        minute=payload["minute"],
        current_score=payload.get("current_score"),
        cashout=payload.get("cashout"),
        aportes=payload.get("aportes", []),
        inplay_summary=payload.get("inplay_summary", {}),
        superbet_event_id=req.superbet_event_id,
    )


@app.post("/user/open-bets", response_model=dict)
def register_open_bet(req: UserOpenBetRequest):
    """Recebe apostas abertas capturadas da Superbet (extensão ou script)."""
    import uuid

    from fastapi import HTTPException

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
                "odds_placed": req.odds_placed,
                "potential_return": req.potential_return,
                "cashout_value": req.cashout_value,
                "ticket_code": req.ticket_code,
                "status": "proposal" if is_proposal else "open",
                "source": req.source,
                "captured_at": req.captured_at
                or __import__("datetime", fromlist=["datetime"]).datetime.now().isoformat(),
                "model_source": req.model_source,
                "combined_ev": req.combined_ev,
                "combined_prob": req.combined_prob,
                "proposal_minute": minute if is_proposal else None,
                "register_minute": minute if not is_proposal else None,
            },
            minute=minute,
            skip_guardrails=is_proposal,
        )
    except BetGuardrailError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return {
        "id": ub.id,
        "message": "Proposta enviada à estação" if is_proposal else "Aposta cadastrada com sucesso",
        "status": ub.status,
        "event_name": ub.event_name,
        "picks_count": len(ub.picks),
        "stake": ub.stake,
        "odds_placed": ub.odds_placed,
        "open_bets_count": len(list_open_bets()),
        "proposals_count": len(list_combo_proposals()),
    }


@app.post("/user/bets/check-against-model", response_model=dict)
def check_bet_against_model(req: CheckAgainstModelRequest):
    """Retorna alerta se palpite 1X2 diverge do modelo pré-jogo e/ou ao vivo."""
    from models.wc_against_model import check_single_bet_against_model

    predictor = _get_wc_predictor()
    alert = check_single_bet_against_model(
        predictor=predictor,
        market=req.market,
        outcome=req.outcome,
        home_team=req.home_team,
        away_team=req.away_team,
        superbet_event_id=req.superbet_event_id,
        phase=req.phase,
        stake=req.stake,
        odds_placed=req.odds_placed,
    )
    return {
        "against_model": alert is not None,
        "alert": alert,
        "message": alert["message"] if alert else "Palpite alinhado ao modelo",
    }


@app.post("/user/open-bets/dedupe", response_model=dict)
def dedupe_user_open_bets():
    """Remove apostas abertas duplicadas (mesmo evento + mercado + palpite)."""
    from api.user_bets_store import dedupe_open_bets_store, list_open_bets

    stats = dedupe_open_bets_store()
    return {
        "message": "Deduplicação concluída",
        **stats,
        "open_bets_count": len(list_open_bets()),
    }


@app.get("/user/open-bets", response_model=dict)
def list_user_open_bets(include_proposals: bool = True):
    """Lista apostas abertas do usuário (opcionalmente propostas da estação)."""
    from api.user_bets_store import list_combo_proposals, list_open_bets

    bets = list_open_bets()
    if include_proposals:
        bets = [*bets, *list_combo_proposals()]
    return {
        "count": len(bets),
        "bets": [
            {
                "id": b.id,
                "event_name": b.event_name,
                "home_team": b.home_team,
                "away_team": b.away_team,
                "picks": [p.model_dump() if hasattr(p, "model_dump") else dict(p) for p in b.picks],
                "stake": b.stake,
                "odds_placed": b.odds_placed,
                "potential_return": b.potential_return,
                "cashout_value": b.cashout_value,
                "ticket_code": b.ticket_code,
                "status": b.status,
                "source": b.source,
                "captured_at": b.captured_at,
            }
            for b in bets
        ],
    }


@app.post("/user/open-bets/refresh-cashouts", response_model=dict)
def refresh_user_open_bets_cashouts(event_id: int | None = None):
    """Consulta cash-out na Superbet para bilhetes abertos com ``ticket_code``."""
    from api.user_bets_store import refresh_open_bets_cashouts

    summary = refresh_open_bets_cashouts(event_id=event_id)
    return {"message": "Cash-out atualizado", **summary}


@app.post("/user/settled-bets/batch", response_model=dict)
def register_settled_bets_batch(req: SettledBetsBatchRequest):
    """Recebe lote de apostas finalizadas (won/lost/cashout) da extensão."""
    from api.user_bets_store import add_settled_bets_batch

    bets_data = [b.model_dump(mode="json") for b in req.bets]
    # Converter picks para dicts se necessário
    for bd in bets_data:
        bd["picks"] = [
            p if isinstance(p, dict) else p.model_dump() for p in bd.get("picks", [])
        ]
    added = add_settled_bets_batch(bets_data)
    return {"added": added, "total_received": len(req.bets), "message": f"{added} apostas novas"}


@app.get("/user/settled-bets", response_model=dict)
def list_user_settled_bets():
    """Lista todas as apostas finalizadas do usuário."""
    from api.user_bets_store import list_settled_bets

    bets = list_settled_bets()
    return {
        "count": len(bets),
        "bets": [b.model_dump(mode="json") for b in bets],
    }


@app.get("/user/bet-performance", response_model=dict)
def get_user_bet_performance():
    """Retorna análise de performance com ROI, padrões de perda e sugestões."""
    from api.user_bets_store import list_settled_bets
    from models.wc_bet_performance import analyze_performance, performance_report_to_dict

    bets = list_settled_bets()
    if not bets:
        return {"error": None, "report": None, "message": "Nenhuma aposta finalizada encontrada."}

    bets_data = [b.model_dump(mode="json") for b in bets]
    report = analyze_performance(bets_data)
    from models.bet_observability import update_roi_by_market

    update_roi_by_market({m.market: m.roi_pct for m in report.by_market})
    return {"error": None, "report": performance_report_to_dict(report)}


@app.get("/observability/bets")
def bet_observability_metrics():
    """Métricas de palpites gerados, bloqueios EV e ROI por mercado."""
    from models.bet_observability import get_bet_observability_metrics

    return get_bet_observability_metrics()


# ---------------------------------------------------------------------------
# Fase 4 — Carteira & Reconciliação (CSV Superbet)
# ---------------------------------------------------------------------------


@app.get("/user/wallet/sync-status", response_model=dict)
def get_wallet_sync_status(user_id: str = Query("default")):
    """Status da inbox CSV e último upload (banner de carteira desatualizada)."""
    from ingest.user_transactions.wallet_inbox import get_wallet_sync_status as _status

    return _status(user_id)


@app.post("/user/wallet/import-inbox", response_model=dict)
def import_wallet_inbox(user_id: str = Query("default")):
    """Importa CSVs pendentes na inbox e reconcilia."""
    from ingest.user_transactions.wallet_inbox import scan_inbox

    if not settings.wallet_inbox_enabled:
        raise HTTPException(status_code=503, detail="Wallet inbox desabilitada")
    outcome = scan_inbox(user_id, reconcile=True)
    return outcome.to_dict()


@app.post("/user/transactions/upload", response_model=dict)
async def upload_user_transactions(
    user_id: str = Query("default", description="ID do usuário dono do CSV"),
    file: UploadFile = File(...),
):
    """Recebe CSV de transações da Superbet e persiste no bronze do datalake."""
    import uuid as _uuid

    from ingest.user_transactions.parser import parse_user_csv
    from ingest.user_transactions.store import save_transactions_bronze

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Arquivo deve ser .csv")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=413, detail="CSV maior que 10MB")

    upload_id = str(_uuid.uuid4())
    rows = parse_user_csv(content, user_id, upload_id)
    if not rows:
        raise HTTPException(status_code=422, detail="Nenhuma linha válida no CSV")

    out_path = save_transactions_bronze(rows, user_id, upload_id)

    n_inplay_placed = sum(1 for r in rows if r.is_inplay_bet and r.is_bet_placed)
    n_wins = sum(1 for r in rows if r.is_win)
    total_staked = sum(r.amount for r in rows if r.is_bet_placed)
    total_won = sum(r.amount for r in rows if r.is_win)

    return {
        "upload_id": upload_id,
        "user_id": user_id,
        "n_rows": len(rows),
        "n_inplay_bets_placed": n_inplay_placed,
        "n_wins": n_wins,
        "total_staked": round(total_staked, 2),
        "total_won": round(total_won, 2),
        "pnl": round(total_won - total_staked, 2),
        "file_path": str(out_path),
        "message": "ok",
    }


@app.get("/user/transactions/summary", response_model=dict)
def get_user_wallet_summary(user_id: str = Query("default")):
    """KPIs agregados da carteira do usuário."""
    from pipelines.user_bet_analytics import compute_wallet_summary
    return compute_wallet_summary(user_id)


@app.post("/user/transactions/reconcile", response_model=dict)
def reconcile_user_bets(user_id: str = Query("default")):
    """Reconcilia transações com snapshots de eventos. Persiste silver."""
    from pipelines.user_bet_reconciliation import (
        reconcile_user_transactions,
        save_reconciliation,
    )

    df = reconcile_user_transactions(user_id)
    if df.empty:
        return {"status": "empty", "n_pairs": 0}

    path = save_reconciliation(df, user_id)
    n_matched = int((df["match_confidence"].fillna(0) >= 0.5).sum())
    return {
        "status": "ok",
        "n_pairs": len(df),
        "n_matched_high_confidence": n_matched,
        "match_rate": round(n_matched / len(df), 3),
        "file_path": str(path),
    }


@app.get("/user/transactions/reconciliation", response_model=dict)
def get_user_reconciliation(
    user_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Tabela paginada da reconciliação aposta-modelo."""
    from pipelines.user_bet_analytics import compute_reconciliation_table
    return compute_reconciliation_table(user_id, limit=limit, offset=offset)


@app.get("/user/transactions/model-errors", response_model=dict)
def get_user_model_errors(user_id: str = Query("default")):
    """Heatmap de erros do modelo por bucket de minuto/score."""
    from pipelines.user_bet_analytics import compute_model_errors_heatmap
    return compute_model_errors_heatmap(user_id)


@app.post("/worldcup/inplay", response_model=WcInPlayResponse)
def worldcup_inplay(req: WcInPlayRequest):
    """Mercados ao vivo condicionados ao placar e minuto (Monte Carlo no tempo restante)."""
    from ingest.superbet.benchmark import market_benchmark
    from ingest.superbet.client import SuperbetClient, SuperbetClientError
    from ingest.superbet.store import merge_snapshot_into_odds_file, save_event_snapshot
    from models.wc_inplay import inplay_from_predictor

    try:
        predictor = _get_wc_predictor()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    home = normalize_national_team(req.home_team)
    away = normalize_national_team(req.away_team)
    home_score = req.home_score
    away_score = req.away_score
    minute = req.minute
    ht_home = req.ht_home_score
    ht_away = req.ht_away_score
    superbet_payload = None
    benchmark = None
    superbet_snapshot = None

    if req.superbet_event_id is not None:
        try:
            superbet_snapshot = SuperbetClient().fetch_event(req.superbet_event_id)
            save_event_snapshot(superbet_snapshot)
            if req.merge_superbet_odds and superbet_snapshot.h2h_odds:
                merge_snapshot_into_odds_file(superbet_snapshot)
                from pipelines.wc_market_features import load_match_odds_index

                load_match_odds_index.cache_clear()
            superbet_payload = superbet_snapshot.to_dict()
            if superbet_snapshot.inplay:
                home_score = superbet_snapshot.inplay.home_score
                away_score = superbet_snapshot.inplay.away_score
                minute = superbet_snapshot.inplay.minute
                if superbet_snapshot.inplay.ht_home_score is not None:
                    ht_home = superbet_snapshot.inplay.ht_home_score
                    ht_away = superbet_snapshot.inplay.ht_away_score
        except SuperbetClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    from models.wc_market_shrinkage import market_probs_from_h2h_implied

    market_probs = None
    if superbet_snapshot is not None:
        market_probs = market_probs_from_h2h_implied(superbet_snapshot.h2h_implied)

    result = inplay_from_predictor(
        predictor,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        minute=minute,
        phase=req.phase,
        is_neutral=True,
        match_minutes=req.match_minutes,
        ht_home_score=ht_home,
        ht_away_score=ht_away,
        market_probs=market_probs,
    )
    payload = result.to_dict()
    if superbet_snapshot and superbet_snapshot.h2h_implied:
        benchmark = market_benchmark(
            superbet_snapshot,
            model_h2h={
                "1": payload["prob_final_home"],
                "X": payload["prob_final_draw"],
                "2": payload["prob_final_away"],
            },
            model_totals=payload.get("final_line_probs"),
        )
    payload["market_benchmark"] = benchmark
    payload["superbet"] = superbet_payload
    return WcInPlayResponse(**payload)


@app.post("/worldcup/predict", response_model=WcPredictionResponse)
def worldcup_predict(req: WcPredictRequest):
    from ingest.sofascore.client import SofascoreClientError
    from ingest.sofascore.kxl_merge import merge_sofascore_fept

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
            home,
            away,
            phase=req.phase,
            kxl_match=kxl_match,
            season=2026,
            group_name=lookup_2026_group(home, away) if req.phase == "group" else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    response = _wc_prediction_to_response(pred)
    if fept_meta:
        response.model_breakdown.kxl_fept = fept_meta
    return response


@app.post("/worldcup/simulate", response_model=WcSimulationResponse)
def worldcup_simulate(req: WcPredictRequest):
    """Analisa um confronto entre duas seleções com dados reais da FIFA.

    Diferente de /worldcup/predict, este endpoint:
    - Busca escalações oficiais da FIFA (se jogo constar na janela atual)
    - Busca pontos FIFA ao vivo (atualizados a cada jogo)
    - Busca dados enriquecidos do Sofascore (forma, séries, H2H)
    - Retorna predição dos modelos + dados brutos reais
    """
    from models.wc_match_simulator import simulate_match

    try:
        predictor = _get_wc_predictor()
    except ValueError:
        predictor = None

    from datetime import date as date_type

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


def _load_finished_match_results(round_data: dict) -> dict[tuple[str, str], dict[str, Any]]:
    """Placares reais indexados por (mandante, visitante) normalizados."""
    from models.wc_prediction_meta import outcome_from_score
    from schemas.national_teams import normalize_national_team

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
                key = (home, away)
                index[key] = {
                    "actual_score": f"{hs}x{as_}",
                    "actual_outcome": outcome_from_score(hs, as_),
                }
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    return index


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
            cached_actual = cached.get("actual_score")
            if cached_actual == actual.get("actual_score"):
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
            resp = _wc_prediction_to_response(
                pred,
                actual_score=actual.get("actual_score") if actual else None,
                actual_outcome=actual.get("actual_outcome") if actual else None,
            )
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


@app.get("/worldcup/teams", response_model=WcTeamsResponse)
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


@app.get("/worldcup/friendlies", response_model=WcFriendliesResponse)
def worldcup_friendlies(
    team: str = Query(..., description="Seleção (nome canônico em português)"),
    pages: int = Query(2, ge=1, le=5, description="Páginas de histórico Sofascore por seleção"),
    year: int | None = Query(
        None,
        ge=2000,
        le=2100,
        description="Ano do calendário; padrão: ano corrente (UTC)",
    ),
    include_finished: bool = Query(True, description="Incluir amistosos já disputados"),
    include_upcoming: bool = Query(True, description="Incluir amistosos futuros/agendados"),
):
    from datetime import datetime, timezone

    from ingest.sofascore.client import SofascoreClient, SofascoreClientError
    from ingest.sofascore.friendlies import list_team_friendlies, save_friendlies_snapshot

    canonical = normalize_national_team(team)
    filter_year = year if year is not None else datetime.now(timezone.utc).year
    try:
        friendlies = list_team_friendlies(
            canonical,
            pages=pages,
            year=filter_year,
            include_finished=include_finished,
            include_upcoming=include_upcoming,
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

    items = [WcFriendlyItem(**row.to_dict()) for row in friendlies]
    return WcFriendliesResponse(
        team=canonical,
        year=filter_year,
        count=len(items),
        friendlies=items,
    )


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


@app.get("/worldcup/benchmarks/history")
def worldcup_benchmark_history():
    """Histórico de evolução dos modelos (WC, in-play, reconciliação)."""
    from pipelines.model_benchmark_history import history_with_deltas

    payload = history_with_deltas()
    if not payload.get("snapshots"):
        raise HTTPException(
            status_code=404,
            detail="Histórico ausente. Execute: run-model-benchmark --seed-only",
        )
    return payload


@app.get("/worldcup/models/registry")
def worldcup_models_registry():
    """Leaderboard de modelos implementáveis + seleção ativa (MLflow + benchmark local)."""
    from pipelines.mlflow_registry import model_registry_summary

    return model_registry_summary()


@app.get("/worldcup/inplay/ensemble-status")
def worldcup_inplay_ensemble_status(
    user_id: str = Query(default="jamarorn", description="ID do usuário (reconciliação CSV)"),
):
    """Prontidão do ensemble GBM (shadow → produção)."""
    from pipelines.inplay_ensemble_readiness import assess_ensemble_readiness

    return assess_ensemble_readiness(user_id).to_dict()


def _run_wc_retrain_background(*, enable_mlflow: bool = False) -> None:
    global _wc_predictor, _wc_artifact_meta, _wc_models_ready, _wc_train_thread
    from models.wc_artifact import load_or_train_wc_predictor
    from models.wc_train_progress import WcTrainProgressReporter

    reporter = WcTrainProgressReporter(console=False)
    try:
        predictor, manifest = load_or_train_wc_predictor(
            force=True,
            progress=reporter,
            enable_mlflow=enable_mlflow,
        )
        with _wc_train_lock:
            _wc_predictor = predictor
            _wc_artifact_meta = manifest
            _wc_models_ready = True
        _wc_round_cache().invalidate_wc_round_cache()
    except Exception as exc:
        with _wc_train_lock:
            _wc_models_ready = False
        reporter.fail(str(exc))
    finally:
        with _wc_train_lock:
            _wc_train_thread = None


@app.get("/worldcup/train/status")
def worldcup_train_status():
    from models.wc_train_progress import read_train_progress

    state = read_train_progress()
    with _wc_train_lock:
        thread_alive = _wc_train_thread is not None and _wc_train_thread.is_alive()
    if state is None:
        return {
            "status": "running" if thread_alive else "idle",
            "running": thread_alive,
        }
    payload = asdict(state)
    payload["running"] = thread_alive or state.status == "running"
    return payload


@app.post("/worldcup/retrain")
def worldcup_retrain(
    background: bool = Query(False),
    mlflow: bool = Query(False, description="Registra o treino no MLflow"),
):
    global _wc_predictor, _wc_artifact_meta, _wc_models_ready, _wc_train_thread

    if background:
        with _wc_train_lock:
            if _wc_train_thread is not None and _wc_train_thread.is_alive():
                raise HTTPException(status_code=409, detail="Treino WC já em andamento")
            _wc_train_thread = threading.Thread(
                target=_run_wc_retrain_background,
                kwargs={"enable_mlflow": mlflow},
                name="wc-retrain",
                daemon=True,
            )
            _wc_train_thread.start()
        return {"status": "started", "poll": "/worldcup/train/status", "mlflow": mlflow}

    try:
        from models.wc_artifact import load_or_train_wc_predictor
        from models.wc_train_progress import WcTrainProgressReporter

        reporter = WcTrainProgressReporter(console=False)
        _wc_predictor, _wc_artifact_meta = load_or_train_wc_predictor(
            force=True,
            progress=reporter,
            enable_mlflow=mlflow,
        )
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
