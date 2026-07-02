"""Schemas Pydantic compartilhados entre os routers da API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Brasileirão / baseline
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WC — Value / Odds
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WC — Corners
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WC — Predict / Simulate
# ---------------------------------------------------------------------------


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
    kxl_match: Any | None = Field(
        None,
        description="Entrada dinâmica KXL (FECL, FEJU, FEDE, FEPT, FEEM) — opcional",
    )


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
    lineup_source: str | None = Field(None, description="Origem das escalações: fifa ou sofascore")
    enrich_features: dict[str, Any] | None = None
    stats_features: dict[str, Any] | None = None
    model_breakdown: dict[str, Any]
    warnings: list[str]


# ---------------------------------------------------------------------------
# WC — Round / Group / Schedule / Squads / Editions / Validate
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WC — Sofascore
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Live / Superbet
# ---------------------------------------------------------------------------


class WcInPlayRequest(BaseModel):
    home_team: str = Field(..., examples=["Brasil"])
    away_team: str = Field(..., examples=["Egito"])
    home_score: int = Field(..., ge=0, examples=[1])
    away_score: int = Field(..., ge=0, examples=[1])
    minute: int = Field(..., ge=0, le=120, examples=[17])
    phase: str = Field("group", examples=["group"])
    match_minutes: int = Field(90, ge=45, le=120, examples=[90])
    ht_home_score: int | None = Field(None, ge=0)
    ht_away_score: int | None = Field(None, ge=0)
    superbet_event_id: int | None = Field(None, examples=[13247229])
    merge_superbet_odds: bool = Field(False)


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
    market: str = Field(..., examples=["h2h"])
    outcome: str = Field(..., examples=["1"])
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
    optimized_tickets: dict | None = None


class LiveCopilotPickResponse(BaseModel):
    rank: int
    market: str
    outcome: str
    label: str
    rationale: str
    confidence: str
    model_prob: float | None = None
    market_odd: float | None = None
    expected_value: float | None = None
    edge_pp: float | None = None
    suggested_stake_pct: float | None = None


class LiveCopilotBilheteLegResponse(BaseModel):
    rank: int
    market: str
    outcome: str
    label: str
    papel: str = "complemento"
    rationale: str = ""
    market_odd: float | None = None
    model_prob: float | None = None
    expected_value: float | None = None
    edge_pp: float | None = None


class LiveCopilotBilheteResponse(BaseModel):
    tipo: str = "nenhum"
    titulo: str = ""
    resumo: str = ""
    pernas: list[LiveCopilotBilheteLegResponse] = Field(default_factory=list)
    valid: bool = False
    combined_odd: float | None = None
    combined_odd_simple: float | None = None
    pricing_mode: str | None = None
    avisos_correlacao: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class LiveCopilotResponse(BaseModel):
    enabled: bool
    available: bool
    sport: str
    event_id: int
    captured_at: str | None = None
    cached: bool = False
    model: str | None = None
    error: str | None = None
    wait_reason: str | None = None
    momento: str = ""
    acao_agora: str = "aguardar"
    confianca_geral: str = "Baixa"
    picks: list[LiveCopilotPickResponse] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
    bilhete: LiveCopilotBilheteResponse | None = None


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


# ---------------------------------------------------------------------------
# Basquete In-Play
# ---------------------------------------------------------------------------


class BasketAporteAdvice(BaseModel):
    market: str
    outcome: str
    label: str
    model_prob: float
    market_odd: float
    implied_prob: float
    expected_value: float
    edge_pp: float
    kelly_quarter: float
    suggested_stake_pct: float
    suggested_stake_value: float | None = None
    action: str


class BasketConfidence(BaseModel):
    score: float
    label: str
    max_edge_pp: float


class BasketInPlaySummary(BaseModel):
    prob_home_win: float | None = None
    prob_away_win: float | None = None
    expected_final_home: float | None = None
    expected_final_away: float | None = None
    expected_total: float | None = None
    remaining_minutes: float | None = None
    moneyline_probs: dict[str, float] = Field(default_factory=dict)
    spread_probs: dict[str, float] = Field(default_factory=dict)
    total_probs: dict[str, float] = Field(default_factory=dict)
    ppm_home: float | None = None
    ppm_away: float | None = None
    ppm_home_prior: float | None = None
    ppm_away_prior: float | None = None
    match_minutes: int | None = None
    n_simulations: int | None = None
    market_total_line: float | None = None
    market_spread_line: float | None = None
    next_quarter_number: int | None = None
    next_quarter_projection_home: float | None = None
    next_quarter_projection_away: float | None = None


class BasketQuarterScore(BaseModel):
    num: int
    home: int
    away: int


class BasketSuperbetLiveEventResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    sport_id: int
    tournament_id: int | None = None
    utc_date: str | None = None
    betradar_id: str | None = None
    minute: int
    home_score: int
    away_score: int
    period_label: str | None = None
    status: str | None = None
    market_count: int
    h2h_odds: dict[str, float] = Field(default_factory=dict)
    captured_at: str


class BasketSuperbetLiveResponse(BaseModel):
    count: int
    sport_id: int | None
    events: list[BasketSuperbetLiveEventResponse]
    captured_at: str


class BasketSuperbetEventResponse(BaseModel):
    event_id: int
    home_team: str
    away_team: str
    event_name: str
    utc_date: str | None = None
    betradar_id: str | None = None
    is_live: bool
    inplay: dict | None = None
    moneyline_odds: dict[str, float] = Field(default_factory=dict)
    moneyline_implied: dict[str, float] = Field(default_factory=dict)
    spread_odds: dict[str, dict[str, float]] = Field(default_factory=dict)
    spread_implied: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_points_odds: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_points_implied: dict[str, dict[str, float]] = Field(default_factory=dict)
    raw_market_count: int = 0
    captured_at: str
    superbet_stale: bool = False


class BasketSuperbetLiveAdviceResponse(BaseModel):
    home_team: str
    away_team: str
    minute: int
    current_score: str | None = None
    period_label: str | None = None
    status: str | None = None
    basket_periods: list[BasketQuarterScore] = Field(default_factory=list)
    is_finished: bool
    is_live: bool
    superbet_stale: bool
    superbet_event_id: int
    sport_id: int | None = None
    captured_at: str
    h2h_odds: dict[str, float] = Field(default_factory=dict)
    h2h_implied: dict[str, float] = Field(default_factory=dict)
    spread_odds: dict[str, dict[str, float]] = Field(default_factory=dict)
    spread_implied: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_points_odds: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_points_implied: dict[str, dict[str, float]] = Field(default_factory=dict)
    inplay_summary: BasketInPlaySummary = Field(default_factory=BasketInPlaySummary)
    aportes: list[BasketAporteAdvice] = Field(default_factory=list)
    confidence: BasketConfidence | None = None


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


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
