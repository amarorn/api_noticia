import type {
  BrasileiraoRound,
  HealthStatus,
  KxlBaselineBreakdown,
  KxlCollisionBreakdown,
  KxlFeptMeta,
  KxlFeptPlayer,
  KxlLethalityBreakdown,
  KxlTeamSnapshot,
  ModelBreakdown,
  SofascoreResolvedEvent,
  OutcomeLabel,
  RefereeMarkets,
  RefereeProfile,
  RefereeMarketLine,
  ValueBetsReport,
  ValueMatch,
  ValueOutcome,
  WcCornersPrediction,
  WcInPlayPrediction,
  WcPrediction,
  WcRound,
  WcSchedule,
  WcScheduleMatch,
  WcSquadDetail,
  WcSquadsIndex,
  WcGroupStandings,
  WcArtifactHealth,
  WcFriendlies,
  WcFriendlyMatch,
  WcSimulation,
  WcSimulationLineupPlayer,
  SuperbetLiveAdvice,
  SuperbetLiveEvent,
  BasketSuperbetLiveFeed,
  BasketSuperbetLiveAdvice,
  LiveCopilotAgent,
  LiveCopilotTabId,
  LiveCopilotUiAction,
  LiveCopilotUiLeg,
} from "@/domain/entities";

export interface ApiModelBreakdown {
  dixon_coles?: Record<string, number>;
  poisson?: Record<string, number>;
  logistic: Record<string, number>;
  dixon_coles_rho?: number | null;
  poisson_factors?: {
    league_avg: number;
    home_attack: number;
    away_attack: number;
    home_defense: number;
    away_defense: number;
    home_advantage: number;
    elo_factor_home: number;
    elo_factor_away: number;
    lambda_home: number;
    lambda_away: number;
    rho: number;
  } | null;
  holdout_2022_accuracy: number | null;
  ensemble_weights: { dixon_coles?: number; poisson?: number; logistic: number };
  ensemble_brier: number | null;
  kxl_baseline?: {
    "1": number;
    X: number;
    "2": number;
    sector_note?: string;
    home_edge?: number;
    away_edge?: number;
    home_attack_vs_away_def?: number;
    away_attack_vs_home_def?: number;
    home_snapshot?: KxlSnapshotApi | null;
    away_snapshot?: KxlSnapshotApi | null;
  } | null;
  kxl_collision?: {
    "1": number;
    X: number;
    "2": number;
    v_delta?: number;
    sector_note?: string;
    letalidade_note?: string;
    mandante?: KxlCollisionSideApi;
    visitante?: KxlCollisionSideApi;
    notes?: string[];
  } | null;
  kxl_fept?: {
    source: string;
    event_id: number;
    ratings_found: number;
    ratings_missing: number;
    esquema_mandante?: string | null;
    esquema_visitante?: string | null;
    absences_home?: number;
    absences_away?: number;
    referee?: string | null;
    referee_profile?: string | null;
    referee_cards_per_game?: number | null;
    home_players?: Array<{
      name: string;
      position?: string | null;
      line?: string | null;
      sofascore_rating?: number | null;
    }>;
    away_players?: Array<{
      name: string;
      position?: string | null;
      line?: string | null;
      sofascore_rating?: number | null;
    }>;
    auto_merged: boolean;
    note?: string | null;
  } | null;
  monte_carlo?: {
    prob_home: number;
    prob_draw: number;
    prob_away: number;
    expected_goals_home: number;
    expected_goals_away: number;
    over_2_5: number;
    under_2_5: number;
    both_teams_score: number;
    clean_sheet_home: number;
    clean_sheet_away: number;
    top_scores: Record<string, number>;
    n_simulations: number;
    rho_used: number;
  } | null;
}

interface KxlSnapshotApi {
  attack_index: number;
  defense_index: number;
  control_index: number;
  gk_index: number;
  chaos: number;
  shots_per_game: number;
  possession_pct: number;
  counter_attack: number;
  inside_goal_pct: number;
  gk_inside_weakness_pct: number;
}

interface KxlLethalityApi {
  dominant?: string;
  index?: number;
  eacp?: number;
  metodos?: Array<{
    metodo: string;
    ataque_pct: number;
    gk_fraco_pct: number;
    pressao: number;
  }>;
}

interface KxlCollisionSideApi {
  energia: number;
  espaco: number;
  tempo: number;
  vcar_raw: number;
  vesc: number;
  v_eff: number;
  letalidade_gk?: KxlLethalityApi;
  setores?: {
    setor: string;
    colisao: number;
    dna?: number;
    permissividade?: number;
  }[];
}

interface ApiWcPrediction {
  home_team: string;
  away_team: string;
  prediction: string;
  confidence: number;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  poisson_score: string;
  expected_goals: string;
  context: string;
  h2h_summary: string;
  model_breakdown: ApiModelBreakdown;
  max_prob_outcome?: string | null;
  max_prob?: number | null;
  prob_margin?: number | null;
  uncertainty?: string | null;
  pick_reason?: string | null;
  actual_score?: string | null;
  actual_outcome?: string | null;
  prediction_hit?: boolean | null;
}

interface ApiWcRound {
  season: number;
  competition: string;
  phase: string;
  round: number;
  predictions: ApiWcPrediction[];
}

interface ApiBrasileiraoRound {
  round_number: number;
  competition: string;
  predictions: Array<{
    home_team: string;
    away_team: string;
    prediction: string;
    confidence: number;
    reason: string;
    news_count: number;
  }>;
}

interface ApiValueOutcome {
  outcome: string;
  odd: number;
  model_prob: number;
  implied_prob: number;
  expected_value: number;
  fair_odd: number;
  kelly_quarter: number;
}

interface ApiValueMatch {
  home_team: string;
  away_team: string;
  best: ApiValueOutcome | null;
  outcomes: ApiValueOutcome[];
}

interface ApiValueBets {
  matched_games: number;
  total_schedule_games: number;
  source: string;
  captured_at: string | null;
  edges: ApiValueMatch[];
}

function mapOutcome(value: string): OutcomeLabel {
  if (value === "1" || value === "X" || value === "2") return value;
  return "X";
}

function mapSnapshot(raw: KxlSnapshotApi | null | undefined): KxlTeamSnapshot | null {
  if (!raw) return null;
  return {
    attackIndex: raw.attack_index,
    defenseIndex: raw.defense_index,
    controlIndex: raw.control_index,
    gkIndex: raw.gk_index,
    chaos: raw.chaos,
    shotsPerGame: raw.shots_per_game,
    possessionPct: raw.possession_pct,
    counterAttack: raw.counter_attack,
    insideGoalPct: raw.inside_goal_pct,
    gkInsideWeaknessPct: raw.gk_inside_weakness_pct,
  };
}

function mapKxlBaseline(raw: ApiModelBreakdown["kxl_baseline"]): KxlBaselineBreakdown | null {
  if (!raw) return null;
  return {
    probHome: raw["1"] ?? 0,
    probDraw: raw["X"] ?? 0,
    probAway: raw["2"] ?? 0,
    sectorNote: raw.sector_note ?? "",
    homeEdge: raw.home_edge ?? 0,
    awayEdge: raw.away_edge ?? 0,
    homeAttackVsAwayDef: raw.home_attack_vs_away_def ?? 0,
    awayAttackVsHomeDef: raw.away_attack_vs_home_def ?? 0,
    homeSnapshot: mapSnapshot(raw.home_snapshot),
    awaySnapshot: mapSnapshot(raw.away_snapshot),
  };
}

function mapLethalityGk(raw: KxlLethalityApi | undefined): KxlLethalityBreakdown | null {
  if (!raw?.metodos?.length) return null;
  return {
    dominant: raw.dominant ?? "",
    index: raw.index ?? 0,
    eacp: raw.eacp ?? 0,
    metodos: raw.metodos.map((m) => ({
      metodo: m.metodo,
      ataquePct: m.ataque_pct,
      gkFracoPct: m.gk_fraco_pct,
      pressao: m.pressao,
    })),
  };
}

function mapKxlCollision(raw: ApiModelBreakdown["kxl_collision"]): KxlCollisionBreakdown | null {
  if (!raw?.mandante || !raw.visitante) return null;
  const mapSide = (side: KxlCollisionSideApi) => ({
    energia: side.energia,
    espaco: side.espaco,
    tempo: side.tempo,
    vcarRaw: side.vcar_raw,
    vesc: side.vesc,
    vEff: side.v_eff,
    lethalityGk: mapLethalityGk(side.letalidade_gk),
    setores: (side.setores ?? []).map((s) => ({
      setor: s.setor,
      colisao: s.colisao,
      attackDna: s.dna,
      permissividade: s.permissividade,
    })),
  });
  return {
    probHome: raw["1"] ?? 0,
    probDraw: raw["X"] ?? 0,
    probAway: raw["2"] ?? 0,
    vDelta: raw.v_delta ?? 0,
    sectorNote: raw.sector_note ?? "",
    lethalityNote: raw.letalidade_note ?? "",
    home: mapSide(raw.mandante),
    away: mapSide(raw.visitante),
    notes: raw.notes ?? [],
  };
}

function mapKxlFeptPlayer(raw: {
  name: string;
  position?: string | null;
  line?: string | null;
  sofascore_rating?: number | null;
}): KxlFeptPlayer {
  return {
    name: raw.name,
    position: raw.position ?? null,
    line: raw.line ?? null,
    sofascoreRating: raw.sofascore_rating ?? null,
  };
}

function mapKxlFept(raw: ApiModelBreakdown["kxl_fept"]): KxlFeptMeta | null {
  if (!raw) return null;
  return {
    source: raw.source,
    eventId: raw.event_id,
    ratingsFound: raw.ratings_found,
    ratingsMissing: raw.ratings_missing,
    esquemaMandante: raw.esquema_mandante ?? null,
    esquemaVisitante: raw.esquema_visitante ?? null,
    homePlayers: raw.home_players?.map(mapKxlFeptPlayer),
    awayPlayers: raw.away_players?.map(mapKxlFeptPlayer),
    absencesHome: raw.absences_home,
    absencesAway: raw.absences_away,
    referee: raw.referee ?? null,
    refereeProfile: raw.referee_profile ?? null,
    refereeCardsPerGame: raw.referee_cards_per_game ?? null,
    autoMerged: raw.auto_merged,
    note: raw.note ?? null,
  };
}

export function mapSofascoreResolvedEvent(raw: {
  event_id: number;
  home_team: string;
  away_team: string;
  match_date: string;
  sofascore_home?: string | null;
  sofascore_away?: string | null;
}): SofascoreResolvedEvent {
  return {
    eventId: raw.event_id,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    matchDate: raw.match_date,
    sofascoreHome: raw.sofascore_home ?? null,
    sofascoreAway: raw.sofascore_away ?? null,
  };
}

export function mapModelBreakdown(raw: ApiModelBreakdown): ModelBreakdown {
  const dc = raw.dixon_coles ?? raw.poisson ?? {};
  const dcWeight = raw.ensemble_weights.dixon_coles ?? raw.ensemble_weights.poisson ?? 0;
  const pf = raw.poisson_factors;
  return {
    dixonColes: {
      "1": dc["1"] ?? 0,
      X: dc["X"] ?? 0,
      "2": dc["2"] ?? 0,
    },
    logistic: {
      "1": raw.logistic["1"] ?? 0,
      X: raw.logistic["X"] ?? 0,
      "2": raw.logistic["2"] ?? 0,
    },
    dixonColesRho: raw.dixon_coles_rho ?? null,
    poissonFactors: pf
      ? {
          leagueAvg: pf.league_avg,
          homeAttack: pf.home_attack,
          awayAttack: pf.away_attack,
          homeDefense: pf.home_defense,
          awayDefense: pf.away_defense,
          homeAdvantage: pf.home_advantage,
          eloFactorHome: pf.elo_factor_home,
          eloFactorAway: pf.elo_factor_away,
          lambdaHome: pf.lambda_home,
          lambdaAway: pf.lambda_away,
          rho: pf.rho,
        }
      : null,
    holdout2022Accuracy: raw.holdout_2022_accuracy,
    ensembleWeights: {
      dixonColes: dcWeight,
      logistic: raw.ensemble_weights.logistic,
    },
    ensembleBrier: raw.ensemble_brier,
    kxlBaseline: mapKxlBaseline(raw.kxl_baseline),
    kxlCollision: mapKxlCollision(raw.kxl_collision),
    kxlFept: mapKxlFept(raw.kxl_fept),
    monteCarlo: raw.monte_carlo
      ? {
          probHome: raw.monte_carlo.prob_home,
          probDraw: raw.monte_carlo.prob_draw,
          probAway: raw.monte_carlo.prob_away,
          expectedGoalsHome: raw.monte_carlo.expected_goals_home,
          expectedGoalsAway: raw.monte_carlo.expected_goals_away,
          over25: raw.monte_carlo.over_2_5,
          under25: raw.monte_carlo.under_2_5,
          bothTeamsScore: raw.monte_carlo.both_teams_score,
          cleanSheetHome: raw.monte_carlo.clean_sheet_home,
          cleanSheetAway: raw.monte_carlo.clean_sheet_away,
          topScores: raw.monte_carlo.top_scores,
          nSimulations: raw.monte_carlo.n_simulations,
          rhoUsed: raw.monte_carlo.rho_used,
        }
      : null,
  };
}

function mapWcPrediction(raw: ApiWcPrediction): WcPrediction {
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    prediction: mapOutcome(raw.prediction),
    confidence: raw.confidence,
    probHome: raw.prob_home,
    probDraw: raw.prob_draw,
    probAway: raw.prob_away,
    poissonScore: raw.poisson_score,
    expectedGoals: raw.expected_goals,
    context: raw.context,
    h2hSummary: raw.h2h_summary,
    modelBreakdown: mapModelBreakdown(raw.model_breakdown),
    maxProbOutcome: raw.max_prob_outcome ? mapOutcome(raw.max_prob_outcome) : null,
    maxProb: raw.max_prob ?? null,
    probMargin: raw.prob_margin ?? null,
    uncertainty: (raw.uncertainty as WcPrediction["uncertainty"]) ?? null,
    pickReason: (raw.pick_reason as WcPrediction["pickReason"]) ?? null,
    actualScore: raw.actual_score ?? null,
    actualOutcome: raw.actual_outcome ? mapOutcome(raw.actual_outcome) : null,
    predictionHit: raw.prediction_hit ?? null,
  };
}

function mapValueOutcome(raw: ApiValueOutcome): ValueOutcome {
  return {
    outcome: mapOutcome(raw.outcome),
    odd: raw.odd,
    modelProb: raw.model_prob,
    impliedProb: raw.implied_prob,
    expectedValue: raw.expected_value,
    fairOdd: raw.fair_odd,
    kellyQuarter: raw.kelly_quarter,
  };
}

function mapValueMatch(raw: ApiValueMatch): ValueMatch {
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    best: raw.best ? mapValueOutcome(raw.best) : null,
    outcomes: raw.outcomes.map(mapValueOutcome),
  };
}

export function mapWcRound(raw: ApiWcRound): WcRound {
  return {
    season: raw.season,
    competition: raw.competition,
    phase: raw.phase,
    round: raw.round,
    predictions: raw.predictions.map(mapWcPrediction),
  };
}

export function mapBrasileiraoRound(raw: ApiBrasileiraoRound): BrasileiraoRound {
  return {
    roundNumber: raw.round_number,
    competition: raw.competition,
    predictions: raw.predictions.map((p) => ({
      homeTeam: p.home_team,
      awayTeam: p.away_team,
      prediction: mapOutcome(p.prediction),
      confidence: p.confidence,
      reason: p.reason,
      newsCount: p.news_count,
    })),
  };
}

export function mapValueBets(raw: ApiValueBets): ValueBetsReport {
  return {
    matchedGames: raw.matched_games,
    totalScheduleGames: raw.total_schedule_games,
    source: raw.source,
    capturedAt: raw.captured_at,
    edges: raw.edges.map(mapValueMatch),
  };
}

interface ApiWcScheduleMatch {
  match_id: string;
  home_team: string;
  away_team: string;
  group: string | null;
  round: number;
  phase: string;
  kickoff: string | null;
  venue: string | null;
  city: string | null;
  fifa_stage?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  played?: boolean;
  prediction?: "1" | "X" | "2" | null;
  confidence?: number | null;
  prob_home?: number | null;
  prob_draw?: number | null;
  prob_away?: number | null;
}

interface ApiWcSchedule {
  season: number;
  competition: string;
  phase: string;
  groups: { id: string; teams: string[] }[];
  matchdays: number[];
  matches: ApiWcScheduleMatch[];
  total_matches: number;
  results_synced_at?: string | null;
  predictions_summary?: {
    loaded: number;
    distribution: Record<string, number>;
    draws: number;
  } | null;
}

function mapWcScheduleMatch(raw: ApiWcScheduleMatch): WcScheduleMatch {
  return {
    matchId: raw.match_id,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    group: raw.group,
    round: raw.round,
    phase: raw.phase,
    kickoff: raw.kickoff,
    venue: raw.venue,
    city: raw.city,
    fifaStage: raw.fifa_stage ?? null,
    homeScore: raw.home_score ?? null,
    awayScore: raw.away_score ?? null,
    played: raw.played ?? false,
    prediction: raw.prediction ?? null,
    confidence: raw.confidence ?? null,
    probHome: raw.prob_home ?? null,
    probDraw: raw.prob_draw ?? null,
    probAway: raw.prob_away ?? null,
  };
}

interface ApiWcFriendlyItem {
  event_id: number | null;
  fifa_match_id: string | null;
  sources: string[];
  home_team: string;
  away_team: string;
  match_date: string | null;
  status: string;
  home_score: number | null;
  away_score: number | null;
  tournament: string;
  is_home: boolean;
}

interface ApiWcFriendlies {
  team: string;
  year: number;
  count: number;
  friendlies: ApiWcFriendlyItem[];
  source: string;
}

function mapWcFriendlyMatch(raw: ApiWcFriendlyItem): WcFriendlyMatch {
  return {
    eventId: raw.event_id,
    fifaMatchId: raw.fifa_match_id,
    sources: raw.sources ?? ["sofascore"],
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    matchDate: raw.match_date,
    status: raw.status,
    homeScore: raw.home_score,
    awayScore: raw.away_score,
    tournament: raw.tournament,
    isHome: raw.is_home,
  };
}

export function mapWcFriendlies(raw: ApiWcFriendlies): WcFriendlies {
  return {
    team: raw.team,
    year: raw.year,
    count: raw.count,
    friendlies: raw.friendlies.map(mapWcFriendlyMatch),
    source: raw.source,
  };
}

interface ApiWcSimulationLineupPlayer {
  name: string;
  shirt_number: number | null;
  position: string | null;
  line?: string | null;
  is_captain?: boolean;
  is_starter?: boolean;
  picture_url: string | null;
  sofascore_rating?: number | null;
  yellow_cards?: number;
  red_cards?: number;
}

interface ApiWcSimulation {
  home_team: string;
  away_team: string;
  match_date: string | null;
  prediction: string;
  confidence: number;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  poisson_score?: string | null;
  expected_goals?: string | null;
  fifa_home_lineup: ApiWcSimulationLineupPlayer[] | null;
  fifa_away_lineup: ApiWcSimulationLineupPlayer[] | null;
  fifa_home_bench?: ApiWcSimulationLineupPlayer[] | null;
  fifa_away_bench?: ApiWcSimulationLineupPlayer[] | null;
  fifa_home_tactics: string | null;
  fifa_away_tactics: string | null;
  fifa_home_coach: string | null;
  fifa_away_coach: string | null;
  fifa_stadium: string | null;
  fifa_home_points: number | null;
  fifa_away_points: number | null;
  fifa_points_diff: number | null;
  lineup_source: string | null;
  warnings: string[];
}

function mapWcSimulationLineupPlayer(raw: ApiWcSimulationLineupPlayer): WcSimulationLineupPlayer {
  return {
    name: raw.name,
    shirtNumber: raw.shirt_number,
    position: raw.position,
    line: raw.line ?? null,
    isCaptain: raw.is_captain ?? false,
    pictureUrl: raw.picture_url,
    sofascoreRating: raw.sofascore_rating ?? null,
    yellowCards: raw.yellow_cards ?? 0,
    redCards: raw.red_cards ?? 0,
    isStarter: raw.is_starter ?? true,
  };
}

export function mapWcSimulation(raw: ApiWcSimulation): WcSimulation {
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    matchDate: raw.match_date,
    prediction: mapOutcome(raw.prediction),
    confidence: raw.confidence,
    probHome: raw.prob_home,
    probDraw: raw.prob_draw,
    probAway: raw.prob_away,
    poissonScore: raw.poisson_score ?? null,
    expectedGoals: raw.expected_goals ?? null,
    fifaHomeLineup: raw.fifa_home_lineup?.map(mapWcSimulationLineupPlayer) ?? null,
    fifaAwayLineup: raw.fifa_away_lineup?.map(mapWcSimulationLineupPlayer) ?? null,
    fifaHomeBench: raw.fifa_home_bench?.map(mapWcSimulationLineupPlayer) ?? null,
    fifaAwayBench: raw.fifa_away_bench?.map(mapWcSimulationLineupPlayer) ?? null,
    fifaHomeTactics: raw.fifa_home_tactics,
    fifaAwayTactics: raw.fifa_away_tactics,
    fifaHomeCoach: raw.fifa_home_coach,
    fifaAwayCoach: raw.fifa_away_coach,
    fifaStadium: raw.fifa_stadium,
    fifaHomePoints: raw.fifa_home_points,
    fifaAwayPoints: raw.fifa_away_points,
    fifaPointsDiff: raw.fifa_points_diff,
    lineupSource: raw.lineup_source,
    warnings: raw.warnings ?? [],
  };
}

export function mapWcSchedule(raw: ApiWcSchedule): WcSchedule {
  return {
    season: raw.season,
    competition: raw.competition,
    phase: raw.phase,
    groups: raw.groups.map((g) => ({ id: g.id, teams: g.teams })),
    matchdays: raw.matchdays,
    matches: raw.matches.map(mapWcScheduleMatch),
    totalMatches: raw.total_matches,
    resultsSyncedAt: raw.results_synced_at ?? null,
    predictionsSummary: raw.predictions_summary
      ? {
          loaded: raw.predictions_summary.loaded,
          distribution: raw.predictions_summary.distribution,
          draws: raw.predictions_summary.draws,
        }
      : null,
  };
}

interface ApiWcSquadsIndex {
  season: number;
  competition: string;
  source_url: string;
  updated_at: string;
  team_count: number;
  teams: { team: string; player_count: number }[];
}

interface ApiWcSquadDetail {
  season: number;
  competition: string;
  source_url: string;
  updated_at: string;
  squad: {
    team: string;
    player_count: number;
    sections: {
      role: string;
      position: string;
      players: { name: string; club: string | null }[];
    }[];
  };
}

export function mapWcSquadsIndex(raw: ApiWcSquadsIndex): WcSquadsIndex {
  return {
    season: raw.season,
    competition: raw.competition,
    sourceUrl: raw.source_url,
    updatedAt: raw.updated_at,
    teamCount: raw.team_count,
    teams: raw.teams.map((t) => ({
      team: t.team,
      playerCount: t.player_count,
    })),
  };
}

export function mapWcSquadDetail(raw: ApiWcSquadDetail): WcSquadDetail {
  return {
    season: raw.season,
    competition: raw.competition,
    sourceUrl: raw.source_url,
    updatedAt: raw.updated_at,
    squad: {
      team: raw.squad.team,
      playerCount: raw.squad.player_count,
      sections: raw.squad.sections.map((s) => ({
        role: s.role,
        position: s.position,
        players: s.players.map((p) => ({ name: p.name, club: p.club })),
      })),
    },
  };
}

export function mapHealth(raw: {
  status: string;
  articles_silver: number;
  fixtures: number;
  wc_artifact?: {
    training_metrics?: { holdout_accuracy?: number };
    collab_metrics?: { brier_score?: number };
    ensemble_weights?: { dixon_coles?: number; logistic?: number };
    feature_count?: number;
    loaded_from_cache?: boolean;
  } | null;
}): HealthStatus {
  const art = raw.wc_artifact;
  let wcArtifact: WcArtifactHealth | null = null;
  if (art) {
    wcArtifact = {
      holdoutAccuracy: art.training_metrics?.holdout_accuracy ?? null,
      ensembleBrier: art.collab_metrics?.brier_score ?? null,
      ensembleWeights: art.ensemble_weights,
      featureCount: art.feature_count,
      loadedFromCache: art.loaded_from_cache,
    };
  }
  return {
    status: raw.status,
    articlesSilver: raw.articles_silver,
    fixtures: raw.fixtures,
    wcArtifact,
  };
}

export function mapWcGroupStandings(raw: {
  season: number;
  competition: string;
  simulated: boolean;
  note: string;
  as_of: string;
  n_real_results: number;
  groups: {
    group: string;
    standings: {
      position: number;
      team: string;
      played: number;
      won: number;
      drawn: number;
      lost: number;
      gf: number;
      ga: number;
      gd: number;
      points: number;
      real_points: number;
      real_played: number;
      real_gd: number;
    }[];
  }[];
}): WcGroupStandings {
  return {
    season: raw.season,
    competition: raw.competition,
    simulated: raw.simulated,
    note: raw.note,
    asOf: raw.as_of,
    nRealResults: raw.n_real_results,
    groups: raw.groups.map((g) => ({
      group: g.group,
      standings: g.standings.map((r) => ({
        ...r,
        realPoints: r.real_points ?? 0,
        realPlayed: r.real_played ?? 0,
        realGd: r.real_gd ?? 0,
      })),
    })),
  };
}

interface ApiWcCornersPrediction {
  home_team: string;
  away_team: string;
  data_source: string;
  expected_corners: string;
  expected_total_corners: number;
  most_likely_corners: string;
  prob_home_more_corners: number;
  prob_draw_corners: number;
  prob_away_more_corners: number;
  line_probs: Record<string, number>;
  factors: {
    league_avg: number;
    home_attack: number;
    away_attack: number;
    home_defense: number;
    away_defense: number;
    home_advantage: number;
    elo_factor_home: number;
    elo_factor_away: number;
    lambda_home: number;
    lambda_away: number;
    training_matches: number;
    blend_with_goal_proxy: number;
  };
  training_summary: {
    matches: number;
    teams: number;
    avg_home_corners: number | null;
    avg_away_corners: number | null;
    avg_total_corners: number | null;
  };
}

export function mapWcCornersPrediction(raw: ApiWcCornersPrediction): WcCornersPrediction {
  const f = raw.factors;
  const ts = raw.training_summary;
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    dataSource: raw.data_source,
    expectedCorners: raw.expected_corners,
    expectedTotalCorners: raw.expected_total_corners,
    mostLikelyCorners: raw.most_likely_corners,
    probHomeMoreCorners: raw.prob_home_more_corners,
    probDrawCorners: raw.prob_draw_corners,
    probAwayMoreCorners: raw.prob_away_more_corners,
    lineProbs: raw.line_probs,
    factors: {
      leagueAvg: f.league_avg,
      homeAttack: f.home_attack,
      awayAttack: f.away_attack,
      homeDefense: f.home_defense,
      awayDefense: f.away_defense,
      homeAdvantage: f.home_advantage,
      eloFactorHome: f.elo_factor_home,
      eloFactorAway: f.elo_factor_away,
      lambdaHome: f.lambda_home,
      lambdaAway: f.lambda_away,
      trainingMatches: f.training_matches,
      blendWithGoalProxy: f.blend_with_goal_proxy,
    },
    trainingSummary: {
      matches: ts.matches,
      teams: ts.teams,
      avgHomeCorners: ts.avg_home_corners,
      avgAwayCorners: ts.avg_away_corners,
      avgTotalCorners: ts.avg_total_corners,
    },
  };
}

interface ApiWcInPlayPrediction {
  home_team: string;
  away_team: string;
  current_score: string;
  minute: number;
  match_minutes: number;
  remaining_fraction: number;
  lambda_full_home: number;
  lambda_full_away: number;
  lambda_remaining_home: number;
  lambda_remaining_away: number;
  rho_used: number;
  prob_final_home: number;
  prob_final_draw: number;
  prob_final_away: number;
  prob_ht_home: number;
  prob_ht_draw: number;
  prob_ht_away: number;
  prob_no_more_goals: number;
  prob_next_goal_home: number;
  prob_next_goal_away: number;
  final_line_probs: Record<string, number>;
  remainder_line_probs: Record<string, number>;
  ht_line_probs: Record<string, number>;
  second_half_line_probs: Record<string, number>;
  team_final_line_probs: Record<string, number>;
  top_final_scores: Record<string, number>;
  top_ht_ft: Record<string, number>;
  combo_markets: Record<string, number>;
  btts_final: number;
  n_simulations: number;
  handicap_probs?: Record<string, number>;
  market_benchmark?: {
    h2h?: Record<string, { market: number; model: number; edge: number; odds?: number }>;
    totals?: Record<string, { market_over: number; model_over: number; edge_over: number }>;
  } | null;
  superbet?: Record<string, unknown> | null;
}

export function mapWcInPlayPrediction(raw: ApiWcInPlayPrediction): WcInPlayPrediction {
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    currentScore: raw.current_score,
    minute: raw.minute,
    matchMinutes: raw.match_minutes,
    remainingFraction: raw.remaining_fraction,
    lambdaFullHome: raw.lambda_full_home,
    lambdaFullAway: raw.lambda_full_away,
    lambdaRemainingHome: raw.lambda_remaining_home,
    lambdaRemainingAway: raw.lambda_remaining_away,
    rhoUsed: raw.rho_used,
    probFinalHome: raw.prob_final_home,
    probFinalDraw: raw.prob_final_draw,
    probFinalAway: raw.prob_final_away,
    probHtHome: raw.prob_ht_home,
    probHtDraw: raw.prob_ht_draw,
    probHtAway: raw.prob_ht_away,
    probNoMoreGoals: raw.prob_no_more_goals,
    probNextGoalHome: raw.prob_next_goal_home,
    probNextGoalAway: raw.prob_next_goal_away,
    finalLineProbs: raw.final_line_probs,
    remainderLineProbs: raw.remainder_line_probs,
    htLineProbs: raw.ht_line_probs,
    secondHalfLineProbs: raw.second_half_line_probs,
    teamFinalLineProbs: raw.team_final_line_probs,
    topFinalScores: raw.top_final_scores,
    topHtFt: raw.top_ht_ft,
    comboMarkets: raw.combo_markets,
    bttsFinal: raw.btts_final,
    nSimulations: raw.n_simulations,
    handicapProbs: raw.handicap_probs,
    marketBenchmark: raw.market_benchmark
      ? {
          h2h: raw.market_benchmark.h2h,
          totals: raw.market_benchmark.totals
            ? Object.fromEntries(
                Object.entries(raw.market_benchmark.totals).map(([k, v]) => [
                  k,
                  {
                    marketOver: v.market_over,
                    modelOver: v.model_over,
                    edgeOver: v.edge_over,
                  },
                ]),
              )
            : undefined,
        }
      : null,
  };
}

interface ApiHandicapLine {
  line: number;
  side: string;
  model_prob: number;
  superbet_odd: number | null;
  ev: number | null;
  kelly_stake: number;
  recommendation: string;
}

interface ApiHandicapAnalysis {
  event_id: number;
  home_team: string;
  away_team: string;
  current_score: string;
  minute: number;
  phase: string;
  lines: ApiHandicapLine[];
  best_bet: ApiHandicapLine | null;
  timestamp: string;
}

function mapHandicapLine(raw: ApiHandicapLine) {
  return {
    line: raw.line,
    side: raw.side as "home" | "away",
    modelProb: raw.model_prob,
    superbetOdd: raw.superbet_odd,
    ev: raw.ev,
    kellyStake: raw.kelly_stake,
    recommendation: raw.recommendation,
  };
}

export function mapHandicapAnalysis(raw: ApiHandicapAnalysis) {
  return {
    eventId: raw.event_id,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    currentScore: raw.current_score,
    minute: raw.minute,
    phase: raw.phase,
    lines: raw.lines.map(mapHandicapLine),
    bestBet: raw.best_bet ? mapHandicapLine(raw.best_bet) : null,
    timestamp: raw.timestamp,
  };
}

interface ApiSuperbetLiveEvent {
  event_id: number;
  home_team: string;
  away_team: string;
  event_name: string;
  sport_id: number;
  tournament_id: number | null;
  utc_date: string | null;
  betradar_id: string | null;
  minute: number;
  home_score: number;
  away_score: number;
  period_label: string | null;
  status: string | null;
  market_count: number;
  h2h_odds: Record<string, number>;
  captured_at: string;
  bet_rank_score?: number | null;
  bet_tier?: string | null;
  bet_label?: string | null;
  bet_palpite?: string | null;
  bet_opportunity_count?: number | null;
  bet_top_ev?: number | null;
  bet_top_label?: string | null;
}

interface ApiSuperbetLiveFeed {
  count: number;
  sport_id: number | null;
  events: ApiSuperbetLiveEvent[];
  captured_at: string;
}

interface ApiSuperbetLiveAdvice {
  home_team: string;
  away_team: string;
  minute: number;
  current_score: string | null;
  period_label: string | null;
  status: string | null;
  is_finished: boolean;
  is_live: boolean;
  score_stale?: {
    score_stale?: boolean;
    warnings?: string[];
    scorealarm_goals?: number;
    snapshot_goals?: number;
  } | null;
  superbet_event_id: number;
  betradar_id: string | null;
  captured_at: string | null;
  raw_market_count: number;
  h2h_odds: Record<string, number>;
  h2h_implied: Record<string, number>;
  h2h_overround?: number | null;
  generosity_probs?: Record<string, number>;
  market_benchmark?: {
    h2h?: Record<string, { market: number; model: number; edge: number; odds?: number }>;
    totals?: Record<string, { market_over: number; model_over: number; edge_over: number }>;
  } | null;
  strategy?: Record<string, unknown> | null;
  cashout: Record<string, unknown> | null;
  aportes: Array<Record<string, unknown>>;
  inplay_summary: Record<string, unknown>;
  btts_odds?: Record<string, number>;
  next_goal_odds?: Record<string, number>;
  analysis_coverage?: {
    h2h?: boolean;
    totals?: boolean;
    btts?: boolean;
    next_goal?: boolean;
    combos?: string[];
    first_half?: boolean;
    second_half?: boolean;
    halftime_adjust?: boolean;
    corners?: boolean;
    yellow_cards?: boolean;
  } | null;
  confidence?: {
    score: number;
    label: string;
    reason: string;
    pattern_accuracy?: Record<string, unknown> | null;
  } | null;
  hedge_report?: Record<string, unknown> | null;
  against_model_alerts?: Array<Record<string, unknown>> | null;
  bet_guardrails?: Record<string, unknown> | null;
  half_markets?: Record<string, Record<string, unknown>>;
  first_half_totals?: Record<string, Record<string, number>>;
  second_half_totals?: Record<string, Record<string, number>>;
  half_tickets?: Record<string, unknown> | null;
  viable_2h_markets?: Record<string, unknown> | null;
  optimized_tickets?: Record<string, unknown> | null;
  super_multipla?: Record<string, unknown> | null;
  halftime_report?: Record<string, unknown> | null;
  corners_projection?: Record<string, unknown> | null;
  trend_report?: Record<string, unknown> | null;
  live_stats?: Record<string, unknown> | null;
  scorealarm?: Record<string, unknown> | null;
  match_context?: Record<string, unknown> | null;
  referee_markets?: Record<string, unknown> | null;
  referee_profile?: Record<string, unknown> | null;
}

function mapOptimizedTicketLeg(raw: Record<string, unknown>) {
  return {
    market: String(raw.market ?? ""),
    outcome: String(raw.outcome ?? ""),
    label: String(raw.label ?? ""),
    modelProb: Number(raw.model_prob ?? 0),
    marketOdd: Number(raw.market_odd ?? 0),
    expectedValue: Number(raw.expected_value ?? 0),
    edgePp: Number(raw.edge_pp ?? 0),
    kellyQuarter: Number(raw.kelly_quarter ?? 0),
    classification: String(raw.classification ?? ""),
  };
}

function mapOptimizedTicket(raw: Record<string, unknown>) {
  const validation = (raw.validation as Record<string, unknown>) ?? {};
  return {
    legs: ((raw.legs as Array<Record<string, unknown>>) ?? []).map(mapOptimizedTicketLeg),
    combinedOdd: Number(raw.combined_odd ?? 0),
    combinedProb: Number(raw.combined_prob ?? 0),
    combinedEv: Number(raw.combined_ev ?? 0),
    correlationPenalty: Number(raw.correlation_penalty ?? 0),
    score: Number(raw.score ?? 0),
    stakeBrl: Number(raw.stake_brl ?? 0),
    stakePct: Number(raw.stake_pct ?? 0),
    periodMix: String(raw.period_mix ?? "ft"),
    nLegs: Number(raw.n_legs ?? 0),
    valid: Boolean(raw.valid ?? true),
    validation: {
      valid: Boolean(validation.valid ?? true),
      errors: ((validation.errors as Array<Record<string, unknown>>) ?? []).map((e) => ({
        severity: String(e.severity ?? ""),
        code: String(e.code ?? ""),
        reason: String(e.reason ?? ""),
      })),
      warnings: ((validation.warnings as Array<Record<string, unknown>>) ?? []).map((w) => ({
        severity: String(w.severity ?? ""),
        code: String(w.code ?? ""),
        reason: String(w.reason ?? ""),
      })),
    },
  };
}

function mapOptimizedTickets(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return undefined;
  return {
    tickets_1h: ((raw.tickets_1h as Array<Record<string, unknown>>) ?? []).map(mapOptimizedTicket),
    tickets_2h: ((raw.tickets_2h as Array<Record<string, unknown>>) ?? []).map(mapOptimizedTicket),
    tickets_ft: ((raw.tickets_ft as Array<Record<string, unknown>>) ?? []).map(mapOptimizedTicket),
    tickets_mixed: ((raw.tickets_mixed as Array<Record<string, unknown>>) ?? []).map(mapOptimizedTicket),
  };
}

function mapPatternAccuracy(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  return {
    score: Number(raw.score ?? 0),
    label: String(raw.label ?? "sem_dados"),
    reason: String(raw.reason ?? ""),
    homeHitRate: raw.home_hit_rate != null ? Number(raw.home_hit_rate) : null,
    awayHitRate: raw.away_hit_rate != null ? Number(raw.away_hit_rate) : null,
    patternCount: Number(raw.pattern_count ?? 0),
  };
}

function mapComboLeg(raw: Record<string, unknown>) {
  return {
    rank: Number(raw.rank ?? 0),
    role: String(raw.role ?? ""),
    label: String(raw.label ?? ""),
    stat: String(raw.stat ?? ""),
    period: String(raw.period ?? ""),
    direction: String(raw.direction ?? ""),
    line: raw.line != null ? Number(raw.line) : null,
    hitRate: Number(raw.hit_rate ?? 0),
    hits: Number(raw.hits ?? 0),
    total: Number(raw.total ?? 10),
    patternRef: String(raw.pattern_ref ?? ""),
    score: Number(raw.score ?? 0),
    availableOnBook: raw.available_on_book != null ? Boolean(raw.available_on_book) : undefined,
    bookChecked: raw.book_checked != null ? Boolean(raw.book_checked) : undefined,
    marketOdd: raw.market_odd != null ? Number(raw.market_odd) : null,
    impliedProb: raw.implied_prob != null ? Number(raw.implied_prob) : null,
    expectedValue: raw.expected_value != null ? Number(raw.expected_value) : null,
    edgePp: raw.edge_pp != null ? Number(raw.edge_pp) : null,
    superbetMarket: raw.superbet_market != null ? String(raw.superbet_market) : null,
    superbetPick: raw.superbet_pick != null ? String(raw.superbet_pick) : null,
    lineAdjustment: raw.line_adjustment != null ? String(raw.line_adjustment) : null,
    fairOdd: raw.fair_odd != null ? Number(raw.fair_odd) : null,
  };
}

function mapInplayTicketLeg(raw: Record<string, unknown>) {
  return {
    market: String(raw.market ?? ""),
    outcome: String(raw.outcome ?? ""),
    label: String(raw.label ?? ""),
    modelProb: Number(raw.model_prob ?? 0),
    marketOdd: Number(raw.market_odd ?? 0),
    expectedValue: Number(raw.expected_value ?? 0),
    edgePp: Number(raw.edge_pp ?? 0),
    suggestedStakePct:
      raw.suggested_stake_pct != null ? Number(raw.suggested_stake_pct) : undefined,
    suggestedStakeValue:
      raw.suggested_stake_value != null ? Number(raw.suggested_stake_value) : undefined,
  };
}

function mapInplayTicketCombo(raw: Record<string, unknown>) {
  return {
    id: String(raw.id ?? ""),
    title: String(raw.title ?? ""),
    legs: ((raw.legs as Array<Record<string, unknown>>) ?? []).map(mapInplayTicketLeg),
    combinedOdd: Number(raw.combined_odd ?? 0),
    combinedProb: Number(raw.combined_prob ?? 0),
    combinedEv: Number(raw.combined_ev ?? 0),
    suggestedStakePct: Number(raw.suggested_stake_pct ?? 0),
    suggestedStakeValue: Number(raw.suggested_stake_value ?? 0),
    notes: ((raw.notes as string[]) ?? []).map(String),
  };
}

function mapHalfTickets(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const mapPeriod = (block: Record<string, unknown> | undefined) => ({
    available: Boolean(block?.available),
    closed: Boolean(block?.closed),
    closedReason: block?.closed_reason != null ? String(block.closed_reason) : null,
    singles: ((block?.singles as Array<Record<string, unknown>>) ?? []).map(mapInplayTicketLeg),
    combos: ((block?.combos as Array<Record<string, unknown>>) ?? []).map(mapInplayTicketCombo),
  });
  return {
    firstHalf: mapPeriod(raw.first_half as Record<string, unknown> | undefined),
    secondHalf: mapPeriod(raw.second_half as Record<string, unknown> | undefined),
    mixedCombos: ((raw.mixed_combos as Array<Record<string, unknown>>) ?? []).map(
      mapInplayTicketCombo,
    ),
  };
}

function mapViable2hMarkets(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const chart = (raw.chart as Record<string, unknown>) ?? {};
  return {
    available: Boolean(raw.available),
    closed: Boolean(raw.closed),
    closedReason: raw.closed_reason != null ? String(raw.closed_reason) : null,
    minute: Number(raw.minute ?? 0),
    minutesRemaining: Number(raw.minutes_remaining ?? 0),
    remainingFraction: Number(raw.remaining_fraction ?? 0),
    block2hMinute: Number(raw.block_2h_minute ?? 82),
    minModelProb: Number(raw.min_model_prob ?? 0.06),
    markets: ((raw.markets as Array<Record<string, unknown>>) ?? []).map((m) => ({
      market: String(m.market ?? ""),
      outcome: String(m.outcome ?? "yes"),
      label: String(m.label ?? ""),
      shortLabel: String(m.short_label ?? m.label ?? ""),
      category: String(m.category ?? "other"),
      categoryLabel: String(m.category_label ?? m.category ?? ""),
      modelProb: Number(m.model_prob ?? 0),
      marketOdd: Number(m.market_odd ?? 0),
      impliedProb: Number(m.implied_prob ?? 0),
      expectedValue: Number(m.expected_value ?? 0),
      edgePp: Number(m.edge_pp ?? 0),
      meetsThreshold: Boolean(m.meets_threshold),
      viabilityScore: Number(m.viability_score ?? 0),
    })),
    chart: {
      categories: ((chart.categories as string[]) ?? []).map(String),
      probabilitiesPct: ((chart.probabilities_pct as number[]) ?? []).map(Number),
      evPct: ((chart.ev_pct as number[]) ?? []).map(Number),
    },
  };
}

export function mapComboTicket(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const accuracyRaw = raw.accuracy as Record<string, unknown> | null | undefined;
  return {
    available: Boolean(raw.available),
    title: String(raw.title ?? ""),
    reason: raw.reason != null ? String(raw.reason) : null,
    accuracy: mapPatternAccuracy(accuracyRaw),
    mainBets: ((raw.main_bets as Array<Record<string, unknown>>) ?? []).map(mapComboLeg),
    reserveBets: ((raw.reserve_bets as Array<Record<string, unknown>>) ?? []).map(mapComboLeg),
    strategyNotes: ((raw.strategy_notes as string[]) ?? []).map(String),
    suggestedStakePct: Number(raw.suggested_stake_pct ?? 0),
    suggestedStakeValue: Number(raw.suggested_stake_value ?? 0),
    combinedHitRateEstimate: Number(raw.combined_hit_rate_estimate ?? 0),
    comboOdd: raw.combo_odd != null ? Number(raw.combo_odd) : null,
    comboEv: raw.combo_ev != null ? Number(raw.combo_ev) : null,
    superbetCapturedAt: raw.superbet_captured_at != null ? String(raw.superbet_captured_at) : null,
      bookCoverage: raw.book_coverage
        ? {
            mainAvailable: Number((raw.book_coverage as Record<string, unknown>).main_available ?? 0),
            mainTotal: Number((raw.book_coverage as Record<string, unknown>).main_total ?? 0),
            reserveAvailable: Number((raw.book_coverage as Record<string, unknown>).reserve_available ?? 0),
            reserveTotal: Number((raw.book_coverage as Record<string, unknown>).reserve_total ?? 0),
          }
        : null,
    last10Analysis: mapComboLast10Analysis(raw.last10_analysis as Record<string, unknown> | null),
  };
}

function mapComboLast10Analysis(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const legs = ((raw.legs as Array<Record<string, unknown>>) ?? []).map((leg) => ({
    rank: leg.rank != null ? Number(leg.rank) : null,
    label: String(leg.label ?? ""),
    stat: String(leg.stat ?? ""),
    period: String(leg.period ?? ""),
    direction: String(leg.direction ?? ""),
    line: leg.line != null ? Number(leg.line) : null,
    patternRef: leg.pattern_ref != null ? String(leg.pattern_ref) : null,
    kxlCrossing: {
      hits: Number((leg.kxl_crossing as Record<string, unknown> | undefined)?.hits ?? 0),
      total: Number((leg.kxl_crossing as Record<string, unknown> | undefined)?.total ?? 0),
      hitRate:
        (leg.kxl_crossing as Record<string, unknown> | undefined)?.hit_rate != null
          ? Number((leg.kxl_crossing as Record<string, unknown>).hit_rate)
          : null,
    },
    sofascoreCrossing: {
      hits:
        (leg.sofascore_crossing as Record<string, unknown> | undefined)?.hits != null
          ? Number((leg.sofascore_crossing as Record<string, unknown>).hits)
          : null,
      total:
        (leg.sofascore_crossing as Record<string, unknown> | undefined)?.total != null
          ? Number((leg.sofascore_crossing as Record<string, unknown>).total)
          : null,
      hitRate:
        (leg.sofascore_crossing as Record<string, unknown> | undefined)?.hit_rate != null
          ? Number((leg.sofascore_crossing as Record<string, unknown>).hit_rate)
          : null,
      evaluated:
        (leg.sofascore_crossing as Record<string, unknown> | undefined)?.evaluated != null
          ? Number((leg.sofascore_crossing as Record<string, unknown>).evaluated)
          : null,
    },
    teams: ((leg.teams as Array<Record<string, unknown>>) ?? []).map((team) => ({
      team: String(team.team ?? ""),
      hits: Number(team.hits ?? 0),
      total: Number(team.total ?? 0),
      evaluated: Number(team.evaluated ?? 0),
      hitRate: team.hit_rate != null ? Number(team.hit_rate) : null,
      kxlPattern: team.kxl_pattern
        ? {
            team: String((team.kxl_pattern as Record<string, unknown>).team ?? ""),
            hits: Number((team.kxl_pattern as Record<string, unknown>).hits ?? 0),
            total: Number((team.kxl_pattern as Record<string, unknown>).total ?? 0),
            hitRate:
              (team.kxl_pattern as Record<string, unknown>).hit_rate != null
                ? Number((team.kxl_pattern as Record<string, unknown>).hit_rate)
                : null,
            line:
              (team.kxl_pattern as Record<string, unknown>).line != null
                ? Number((team.kxl_pattern as Record<string, unknown>).line)
                : null,
            source: String((team.kxl_pattern as Record<string, unknown>).source ?? ""),
          }
        : null,
      matches: ((team.matches as Array<Record<string, unknown>>) ?? []).map((m) => ({
        eventId: Number(m.event_id ?? 0),
        matchDate: m.match_date != null ? String(m.match_date) : null,
        homeTeam: String(m.home_team ?? ""),
        awayTeam: String(m.away_team ?? ""),
        metricValue: m.metric_value != null ? Number(m.metric_value) : null,
        hit: m.hit === true ? true : m.hit === false ? false : null,
        detail: String(m.detail ?? ""),
        incidentsSource: m.incidents_source != null ? String(m.incidents_source) : null,
      })),
    })),
  }));
  return {
    windowSize: Number(raw.window_size ?? 10),
    sourceNote: String(raw.source_note ?? ""),
    incidentsFetched: Number(raw.incidents_fetched ?? 0),
    legs,
  };
}

function mapBetStrategy(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const opps = (raw.opportunities as Array<Record<string, unknown>>) ?? [];
  const shields = (raw.shields as Array<Record<string, unknown>>) ?? [];
  const cash = raw.cashout as Record<string, unknown> | null;
  return {
    posture: String(raw.posture ?? "neutro"),
    maxNewExposurePct: Number(raw.max_new_exposure_pct ?? 0),
    maxNewExposureValue: Number(raw.max_new_exposure_value ?? 0),
    opportunityCount: Number(raw.opportunity_count ?? 0),
    strongOpportunityCount: Number(raw.strong_opportunity_count ?? 0),
    minEdgeThreshold: Number(raw.min_edge_threshold ?? 0),
    waitReason: String(raw.wait_reason ?? ""),
    watchList: ((raw.watch_list as Array<Record<string, unknown>>) ?? []).map((w) => ({
      market: String(w.market),
      outcome: String(w.outcome),
      label: String(w.label),
      modelProb: Number(w.model_prob),
      marketOdd: Number(w.market_odd),
      expectedValue: Number(w.expected_value),
      edgePp: Number(w.edge_pp),
      meetsThreshold: Boolean(w.meets_threshold),
    })),
    marketScan: ((raw.market_scan as Array<Record<string, unknown>>) ?? []).map((row) => ({
      market: String(row.market),
      outcome: String(row.outcome),
      label: String(row.label),
      modelProb: Number(row.model_prob),
      marketOdd: Number(row.market_odd),
      impliedProb: Number(row.implied_prob),
      expectedValue: Number(row.expected_value),
      edgePp: Number(row.edge_pp),
      suggestedStakePct: Number(row.suggested_stake_pct),
      suggestedStakeValue: Number(row.suggested_stake_value),
      meetsThreshold: Boolean(row.meets_threshold),
    })),
    opportunities: opps.map((op) => ({
      rank: Number(op.rank),
      market: String(op.market),
      outcome: String(op.outcome),
      label: String(op.label),
      tier: String(op.tier),
      modelProb: Number(op.model_prob),
      marketOdd: Number(op.market_odd),
      impliedProb: op.implied_prob != null ? Number(op.implied_prob) : undefined,
      expectedValue: Number(op.expected_value),
      edgePp: Number(op.edge_pp),
      suggestedStakePct: Number(op.suggested_stake_pct),
      suggestedStakeValue: Number(op.suggested_stake_value),
      action: String(op.action),
      timing: op.timing != null ? String(op.timing) : undefined,
      timingReason: op.timing_reason != null ? String(op.timing_reason) : undefined,
      fundamentacao: op.fundamentacao != null ? String(op.fundamentacao) : undefined,
    })),
    shields: shields.map((s) => ({
      action: String(s.action),
      priority: String(s.priority),
      title: String(s.title),
      reason: String(s.reason),
      market: s.market != null ? String(s.market) : undefined,
      outcome: s.outcome != null ? String(s.outcome) : undefined,
      odd: s.odd != null ? Number(s.odd) : undefined,
      expectedValue: s.expected_value != null ? Number(s.expected_value) : undefined,
    })),
    rules: ((raw.rules as string[]) ?? []).map(String),
    cashout: cash
      ? {
          action: String(cash.action),
          confidence: Number(cash.confidence),
          reason: String(cash.reason),
        }
      : null,
    patternAccuracy: mapPatternAccuracy(raw.pattern_accuracy as Record<string, unknown> | null),
    comboTicket: mapComboTicket(raw.combo_ticket as Record<string, unknown> | null),
    hedgePairStrategies: mapHedgePairStrategies(
      raw.hedge_pair_strategies as Record<string, unknown> | null,
    ),
  };
}

function mapHedgePairLeg(raw: Record<string, unknown>) {
  return {
    market: String(raw.market ?? ""),
    outcome: String(raw.outcome ?? ""),
    label: String(raw.label ?? ""),
    modelProb: Number(raw.model_prob ?? 0),
    marketOdd: Number(raw.market_odd ?? 0),
    expectedValue: Number(raw.expected_value ?? 0),
    edgePp: Number(raw.edge_pp ?? 0),
  };
}

function mapHedgePairStrategies(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const strategiesRaw = (raw.strategies as Array<Record<string, unknown>>) ?? [];
  return {
    enabled: Boolean(raw.enabled),
    available: Boolean(raw.available),
    candidateCount: Number(raw.candidate_count ?? 0),
    error: raw.error != null ? String(raw.error) : null,
    strategies: strategiesRaw.map((s) => {
      const cov = (s.coverage as Record<string, unknown>) ?? {};
      return {
        id: String(s.id ?? ""),
        titulo: String(s.titulo ?? s.name ?? ""),
        resumo: String(s.resumo ?? ""),
        stakeSplit: String(s.stake_split ?? "50% / 50%"),
        cenarioChave: String(s.cenario_chave ?? ""),
        llmEnriched: Boolean(s.llm_enriched),
        stakeHintPct: Number(s.stake_hint_pct ?? 0),
        stakeHintValue: Number(s.stake_hint_value ?? 0),
        scenarioA: String(s.scenario_a ?? ""),
        scenarioB: String(s.scenario_b ?? ""),
        scenarioBoth: String(s.scenario_both ?? ""),
        coverage: {
          probLegA: Number(cov.prob_leg_a ?? 0),
          probLegB: Number(cov.prob_leg_b ?? 0),
          probBothWin: Number(cov.prob_both_win ?? 0),
          probAtLeastOne: Number(cov.prob_at_least_one ?? 0),
          probBothLose: Number(cov.prob_both_lose ?? 0),
        },
        legA: mapHedgePairLeg((s.leg_a as Record<string, unknown>) ?? {}),
        legB: mapHedgePairLeg((s.leg_b as Record<string, unknown>) ?? {}),
      };
    }),
  };
}

function mapLiveStats(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  return {
    source: raw.source != null ? String(raw.source) : null,
    possessionSource:
      raw.possession_source != null ? String(raw.possession_source) : null,
    sofascoreEventId: raw.sofascore_event_id != null ? Number(raw.sofascore_event_id) : null,
    sofascoreAvailable: Boolean(raw.sofascore_available),
    scorealarmAvailable: Boolean(raw.scorealarm_available),
    scorealarmStale: Boolean(raw.scorealarm_stale),
    homeXg: raw.home_xg != null ? Number(raw.home_xg) : null,
    awayXg: raw.away_xg != null ? Number(raw.away_xg) : null,
    homePossessionPct:
      raw.home_possession_pct != null ? Number(raw.home_possession_pct) : null,
    awayPossessionPct:
      raw.away_possession_pct != null ? Number(raw.away_possession_pct) : null,
    homeShotsOnTarget:
      raw.home_shots_on_target != null ? Number(raw.home_shots_on_target) : null,
    awayShotsOnTarget:
      raw.away_shots_on_target != null ? Number(raw.away_shots_on_target) : null,
    homeCorners: raw.home_corners != null ? Number(raw.home_corners) : null,
    awayCorners: raw.away_corners != null ? Number(raw.away_corners) : null,
    homeYellowCards:
      raw.home_yellow_cards != null ? Number(raw.home_yellow_cards) : null,
    awayYellowCards:
      raw.away_yellow_cards != null ? Number(raw.away_yellow_cards) : null,
    homeRedCards:
      raw.home_red_cards != null ? Number(raw.home_red_cards) : null,
    awayRedCards:
      raw.away_red_cards != null ? Number(raw.away_red_cards) : null,
    warnings: ((raw.warnings as string[]) ?? []).map(String),
  };
}

function mapScorealarm(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const h2hRaw = raw.h2h as Record<string, unknown> | null | undefined;
  const prematchRaw = raw.prematch as Record<string, unknown> | null | undefined;
  const socialRaw = raw.social as Record<string, unknown> | null | undefined;
  const mapTeamForm = (teamRaw: Record<string, unknown> | undefined) => ({
    team: String(teamRaw?.team ?? ""),
    form: String(teamRaw?.form ?? ""),
    wins: Number(teamRaw?.wins ?? 0),
    draws: Number(teamRaw?.draws ?? 0),
    losses: Number(teamRaw?.losses ?? 0),
    goalsAvg: Number(teamRaw?.goals_avg ?? 0),
    concededAvg: Number(teamRaw?.conceded_avg ?? 0),
    coach: teamRaw?.coach != null ? String(teamRaw.coach) : null,
    lastMatches: ((teamRaw?.last_matches as Array<Record<string, unknown>>) ?? []).map(
      (m) => ({
        opponent: String(m.opponent ?? ""),
        score: String(m.score ?? ""),
        result: String(m.result ?? ""),
        goalsFor: Number(m.goals_for ?? 0),
        goalsAgainst: Number(m.goals_against ?? 0),
      }),
    ),
  });
  return {
    available: Boolean(raw.available),
    stale: Boolean(raw.stale),
    scoresId: raw.scores_id != null ? String(raw.scores_id) : null,
    timeline: ((raw.timeline as Array<Record<string, unknown>>) ?? []).map((e) => ({
      minute: Number(e.minute ?? 0),
      addedTime: e.added_time != null ? Number(e.added_time) : null,
      team: String(e.team ?? ""),
      side: Number(e.side ?? 0),
      type: Number(e.type ?? 0),
      subtype: Number(e.subtype ?? 0),
      label: String(e.label ?? "Evento"),
      icon: String(e.icon ?? "•"),
      score: e.score != null ? String(e.score) : null,
    })),
    h2h: h2hRaw
      ? {
          homeWins: Number(h2hRaw.home_wins ?? 0),
          draws: Number(h2hRaw.draws ?? 0),
          awayWins: Number(h2hRaw.away_wins ?? 0),
          sinceYear: h2hRaw.since_year != null ? Number(h2hRaw.since_year) : null,
        }
      : null,
    prematch: prematchRaw
      ? {
          home: mapTeamForm(prematchRaw.home as Record<string, unknown>),
          away: mapTeamForm(prematchRaw.away as Record<string, unknown>),
          h2hMatches: (
            (prematchRaw.h2h_matches as Array<Record<string, unknown>>) ?? []
          ).map((m) => ({
            homeTeam: String(m.home_team ?? ""),
            awayTeam: String(m.away_team ?? ""),
            score: String(m.score ?? ""),
          })),
        }
      : null,
    players: ((raw.players as Array<Record<string, unknown>>) ?? []).map((p) => ({
      name: String(p.name ?? ""),
      team: String(p.team ?? ""),
      side: Number(p.side ?? 0),
      jersey: String(p.jersey ?? ""),
      positionLabel: String(p.position_label ?? ""),
      stats: Object.fromEntries(
        Object.entries((p.stats as Record<string, unknown>) ?? {})
          .filter(([, v]) => v != null && !Number.isNaN(Number(v)))
          .map(([k, v]) => [k, Number(v)]),
      ),
      highlights: ((p.highlights as string[]) ?? []).map(String),
    })),
    social: socialRaw
      ? {
          available: Boolean(socialRaw.available),
          source: String(socialRaw.source ?? "social-front"),
          reason: socialRaw.reason != null ? String(socialRaw.reason) : null,
          picks: ((socialRaw.picks as Array<Record<string, unknown>>) ?? []).map((pick) => ({
            label: String(pick.label ?? ""),
            market: String(pick.market ?? ""),
            outcome: String(pick.outcome ?? ""),
            odd: pick.odd != null ? Number(pick.odd) : null,
            betCount: pick.bet_count != null ? Number(pick.bet_count) : null,
            sharePct: pick.share_pct != null ? Number(pick.share_pct) : null,
          })),
        }
      : null,
    stats: Object.fromEntries(
      Object.entries((raw.stats as Record<string, unknown>) ?? {})
        .filter(([, v]) => v != null && !Number.isNaN(Number(v)))
        .map(([k, v]) => [k, Number(v)]),
    ),
  };
}

function mapTrendReport(raw: Record<string, unknown> | null | undefined) {
  if (!raw) return null;
  const advice = raw.position_advice as Record<string, unknown> | null | undefined;
  return {
    eventId: Number(raw.event_id ?? 0),
    homeTeam: String(raw.home_team ?? ""),
    awayTeam: String(raw.away_team ?? ""),
    currentScore: raw.current_score != null ? String(raw.current_score) : null,
    minute: Number(raw.minute ?? 0),
    dominantTrend: raw.dominant_trend != null ? String(raw.dominant_trend) : null,
    signals: ((raw.signals as Array<Record<string, unknown>>) ?? []).map((s) => ({
      type: String(s.type ?? ""),
      direction: String(s.direction ?? ""),
      strength: Number(s.strength ?? 0),
      description: String(s.description ?? ""),
      minute: s.minute != null ? Number(s.minute) : null,
    })),
    positionAdvice: advice
      ? {
          action: String(advice.action ?? ""),
          urgency: String(advice.urgency ?? ""),
          reasoning: String(advice.reasoning ?? ""),
          repositionTo: advice.reposition_to != null ? String(advice.reposition_to) : null,
          repositionDetail:
            advice.reposition_detail != null ? String(advice.reposition_detail) : null,
          repositionOdd: advice.reposition_odd != null ? Number(advice.reposition_odd) : null,
          confidence: Number(advice.confidence ?? 0),
        }
      : null,
    bestOpportunities: ((raw.best_opportunities as Array<Record<string, unknown>>) ?? []).map(
      (item) => ({ ...item }),
    ),
  };
}

function mapCornersProjection(raw: Record<string, unknown>) {
  const lineProbs = (raw.line_probs as Record<string, number>) ?? {};
  return {
    source: String(raw.source ?? "live_poisson"),
    minute: Number(raw.minute ?? 0),
    observedHome: Number(raw.observed_home ?? 0),
    observedAway: Number(raw.observed_away ?? 0),
    observedTotal: Number(raw.observed_total ?? 0),
    expectedRemainingHome: Number(raw.expected_remaining_home ?? 0),
    expectedRemainingAway: Number(raw.expected_remaining_away ?? 0),
    expectedFtHome: Number(raw.expected_ft_home ?? 0),
    expectedFtAway: Number(raw.expected_ft_away ?? 0),
    expectedFtTotal: Number(raw.expected_ft_total ?? 0),
    probHomeMoreCorners: Number(raw.prob_home_more_corners ?? 0),
    probDrawCorners: Number(raw.prob_draw_corners ?? 0),
    probAwayMoreCorners: Number(raw.prob_away_more_corners ?? 0),
    mostLikelyCorners: String(raw.most_likely_corners ?? ""),
    lineProbs,
  };
}

function mapHalftimeReport(raw: Record<string, unknown>) {
  const frozen = (raw.frozen_stats as Record<string, unknown>) ?? {};
  const goal = (raw.goal_adjustment as Record<string, unknown>) ?? {};
  const corners = (raw.corners as Record<string, unknown>) ?? {};
  const cards = (raw.cards as Record<string, unknown>) ?? {};
  return {
    applied: Boolean(raw.applied),
    summary: String(raw.summary ?? ""),
    frozenStats: {
      htHomeScore: Number(frozen.ht_home_score ?? 0),
      htAwayScore: Number(frozen.ht_away_score ?? 0),
      homeCorners1h: Number(frozen.home_corners_1h ?? 0),
      awayCorners1h: Number(frozen.away_corners_1h ?? 0),
      homeYellows1h: Number(frozen.home_yellows_1h ?? 0),
      awayYellows1h: Number(frozen.away_yellows_1h ?? 0),
      frozenAt: String(frozen.frozen_at ?? ""),
    },
    goalAdjustment: {
      home2hFactor: Number(goal.home_2h_factor ?? 1),
      away2hFactor: Number(goal.away_2h_factor ?? 1),
      reasons: ((goal.reasons as string[]) ?? []).map(String),
    },
    corners: {
      observed1hHome: Number(corners.observed_1h_home ?? 0),
      observed1hAway: Number(corners.observed_1h_away ?? 0),
      expected2hHome: Number(corners.expected_2h_home ?? 0),
      expected2hAway: Number(corners.expected_2h_away ?? 0),
      expectedFtTotal: Number(corners.expected_ft_total ?? 0),
      probHomeMoreCorners:
        corners.prob_home_more_corners != null
          ? Number(corners.prob_home_more_corners)
          : undefined,
    },
    cards: {
      observed1hTotal: Number(cards.observed_1h_total ?? 0),
      expected2hTotal: Number(cards.expected_2h_total ?? 0),
      expectedFtTotal: Number(cards.expected_ft_total ?? 0),
    },
    cornerLineProbs: (raw.corner_line_probs as Record<string, number>) ?? {},
    cardLineProbs: (raw.card_line_probs as Record<string, number>) ?? {},
  };
}

export function mapSuperbetLiveAdvice(raw: ApiSuperbetLiveAdvice) {
  const cash = raw.cashout;
  const summary = raw.inplay_summary ?? {};
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    minute: raw.minute,
    currentScore: raw.current_score,
    periodLabel: raw.period_label,
    status: raw.status,
    isFinished: raw.is_finished,
    isLive: raw.is_live,
    scoreStale: raw.score_stale
      ? {
          scoreStale: Boolean((raw.score_stale as Record<string, unknown>).score_stale),
          warnings: (
            ((raw.score_stale as Record<string, unknown>).warnings as string[]) ?? []
          ).map(String),
          scorealarmGoals: (raw.score_stale as Record<string, unknown>).scorealarm_goals as
            | number
            | undefined,
          snapshotGoals: (raw.score_stale as Record<string, unknown>).snapshot_goals as
            | number
            | undefined,
        }
      : null,
    superbetEventId: raw.superbet_event_id,
    betradarId: raw.betradar_id,
    capturedAt: raw.captured_at,
    rawMarketCount: raw.raw_market_count,
    h2hOdds: raw.h2h_odds ?? {},
    h2hImplied: raw.h2h_implied ?? {},
    h2hOverround: raw.h2h_overround ?? null,
    generosityProbs: raw.generosity_probs ?? {},
    confidence: raw.confidence
      ? {
          score: Number(raw.confidence.score ?? 0),
          label: String(raw.confidence.label ?? ""),
          reason: String(raw.confidence.reason ?? ""),
          patternAccuracy: raw.confidence.pattern_accuracy
            ? mapPatternAccuracy(raw.confidence.pattern_accuracy as Record<string, unknown>)
            : null,
        }
      : null,
    marketBenchmark: raw.market_benchmark
      ? {
          h2h: raw.market_benchmark.h2h,
          totals: raw.market_benchmark.totals
            ? Object.fromEntries(
                Object.entries(raw.market_benchmark.totals).map(([k, v]) => [
                  k,
                  {
                    marketOver: v.market_over,
                    modelOver: v.model_over,
                    edgeOver: v.edge_over,
                  },
                ]),
              )
            : undefined,
        }
      : null,
    strategy: mapBetStrategy(raw.strategy as Record<string, unknown> | null),
    cashout: cash
      ? {
          action: String(cash.action),
          confidence: Number(cash.confidence),
          reason: String(cash.reason),
          currentModelProb: Number(cash.current_model_prob),
          placedImpliedProb:
            cash.placed_implied_prob != null ? Number(cash.placed_implied_prob) : undefined,
          remainingEv: Number(cash.remaining_ev),
          estimatedFairCashout: Number(cash.estimated_fair_cashout),
          potentialReturn: Number(cash.potential_return),
          trendInfluenced: cash.trend_influenced === true,
          trendUrgency:
            cash.trend_urgency != null ? String(cash.trend_urgency) : undefined,
        }
      : null,
    aportes: (raw.aportes ?? []).map((a) => ({
      label: String(a.label),
      market: String(a.market),
      outcome: String(a.outcome),
      modelProb: Number(a.model_prob),
      marketOdd: Number(a.market_odd),
      expectedValue: Number(a.expected_value),
      edgePp: Number(a.edge_pp),
      suggestedStakePct: Number(a.suggested_stake_pct),
      suggestedStakeValue: Number(a.suggested_stake_value),
      action: String(a.action),
    })),
    inplaySummary: {
      probFinalHome: Number(summary.prob_final_home ?? 0),
      probFinalDraw: Number(summary.prob_final_draw ?? 0),
      probFinalAway: Number(summary.prob_final_away ?? 0),
      probHtHome: summary.prob_ht_home as number | undefined,
      probHtDraw: summary.prob_ht_draw as number | undefined,
      probHtAway: summary.prob_ht_away as number | undefined,
      probShHome: summary.prob_sh_home as number | undefined,
      probShDraw: summary.prob_sh_draw as number | undefined,
      probShAway: summary.prob_sh_away as number | undefined,
      over25: summary.over_2_5 as number | undefined,
      btts: summary.btts as number | undefined,
      probNextGoalHome: summary.prob_next_goal_home as number | undefined,
      probNextGoalAway: summary.prob_next_goal_away as number | undefined,
      probNoMoreGoals: summary.prob_no_more_goals as number | undefined,
      topFinalScores: summary.top_final_scores as Record<string, number> | undefined,
      htCorrectScores: summary.ht_correct_scores as Record<string, number> | undefined,
      shCorrectScores: summary.sh_correct_scores as Record<string, number> | undefined,
      htExactTotals: summary.ht_exact_totals as Record<string, number> | undefined,
      shExactTotals: summary.sh_exact_totals as Record<string, number> | undefined,
      htLineProbs: summary.ht_line_probs as Record<string, number> | undefined,
      secondHalfLineProbs: summary.second_half_line_probs as Record<string, number> | undefined,
      htHandicapProbs: summary.ht_handicap_probs as Record<string, number> | undefined,
      shHandicapProbs: summary.sh_handicap_probs as Record<string, number> | undefined,
      ftHandicapProbs: summary.ft_handicap_probs as Record<string, number> | undefined,
      ftAsianHandicapProbs: summary.ft_asian_handicap_probs as Record<string, number> | undefined,
      cornerLineProbs: summary.corner_line_probs as Record<string, number> | undefined,
      cardLineProbs: summary.card_line_probs as Record<string, number> | undefined,
      refereeMarkets: raw.referee_markets
        ? mapRefereeMarkets(raw.referee_markets as Record<string, unknown>)
        : undefined,
      refereeProfile: raw.referee_profile
        ? mapRefereeProfile(raw.referee_profile as Record<string, unknown>)
        : undefined,
      halftimeAdjustment: summary.halftime_adjustment
        ? {
            applied: Boolean(
              (summary.halftime_adjustment as Record<string, unknown>).applied,
            ),
            home2hFactor: Number(
              (summary.halftime_adjustment as Record<string, unknown>).home_2h_factor ?? 1,
            ),
            away2hFactor: Number(
              (summary.halftime_adjustment as Record<string, unknown>).away_2h_factor ?? 1,
            ),
            reasons: (
              ((summary.halftime_adjustment as Record<string, unknown>).reasons as string[]) ??
              []
            ).map(String),
          }
        : undefined,
      lambdaAdjustment: summary.lambda_adjustment
        ? {
            lambdaPriorHome: Number(
              (summary.lambda_adjustment as Record<string, unknown>).lambda_prior_home ?? 0,
            ),
            lambdaPriorAway: Number(
              (summary.lambda_adjustment as Record<string, unknown>).lambda_prior_away ?? 0,
            ),
            lambdaFullHome: Number(
              (summary.lambda_adjustment as Record<string, unknown>).lambda_full_home ?? 0,
            ),
            lambdaFullAway: Number(
              (summary.lambda_adjustment as Record<string, unknown>).lambda_full_away ?? 0,
            ),
            deltaHome: Number(
              (summary.lambda_adjustment as Record<string, unknown>).delta_home ?? 0,
            ),
            deltaAway: Number(
              (summary.lambda_adjustment as Record<string, unknown>).delta_away ?? 0,
            ),
            steps: ((summary.lambda_adjustment as Record<string, unknown>).steps as unknown[])?.map(
              (step) => step as Record<string, unknown>,
            ),
          }
        : undefined,
      modelBeforeDate:
        typeof summary.model_before_date === "string" ? summary.model_before_date : null,
    },
    halfMarkets: (raw.half_markets as SuperbetLiveAdvice["halfMarkets"]) ?? undefined,
    firstHalfTotals: raw.first_half_totals ?? undefined,
    secondHalfTotals: raw.second_half_totals ?? undefined,
    bttsOdds: raw.btts_odds ?? {},
    nextGoalOdds: raw.next_goal_odds ?? {},
    analysisCoverage: raw.analysis_coverage
      ? {
          h2h: Boolean(raw.analysis_coverage.h2h),
          totals: Boolean(raw.analysis_coverage.totals),
          btts: Boolean(raw.analysis_coverage.btts),
          nextGoal: Boolean(raw.analysis_coverage.next_goal),
          combos: ((raw.analysis_coverage.combos as string[]) ?? []).map(String),
          firstHalf: Boolean(raw.analysis_coverage.first_half),
          secondHalf: Boolean(raw.analysis_coverage.second_half),
          halftimeAdjust: Boolean(raw.analysis_coverage.halftime_adjust),
          corners: Boolean(raw.analysis_coverage.corners),
          yellowCards: Boolean(raw.analysis_coverage.yellow_cards),
        }
      : null,
    halftimeReport: raw.halftime_report
      ? mapHalftimeReport(raw.halftime_report as Record<string, unknown>)
      : null,
    cornersProjection: raw.corners_projection
      ? mapCornersProjection(raw.corners_projection as Record<string, unknown>)
      : null,
    hedgeReport: (raw.hedge_report as SuperbetLiveAdvice["hedgeReport"]) ?? null,
    againstModelAlerts: ((raw.against_model_alerts as Array<Record<string, unknown>>) ?? []).map(
      (a) => ({
        betId: a.bet_id != null ? String(a.bet_id) : null,
        market: String(a.market ?? "h2h"),
        betOutcome: mapOutcome(String(a.bet_outcome ?? "X")),
        betOutcomeLabel: String(a.bet_outcome_label ?? ""),
        stake: Number(a.stake ?? 0),
        oddsPlaced: a.odds_placed != null ? Number(a.odds_placed) : null,
        pregamePalpite: mapOutcome(String(a.pregame_palpite ?? "X")),
        pregameProb: Number(a.pregame_prob ?? 0),
        pregameUncertainty: a.pregame_uncertainty != null ? String(a.pregame_uncertainty) : null,
        inplayPalpite: mapOutcome(String(a.inplay_palpite ?? "X")),
        inplayProb: Number(a.inplay_prob ?? 0),
        inplayProbs: {
          "1": Number((a.inplay_probs as Record<string, number> | undefined)?.["1"] ?? 0),
          X: Number((a.inplay_probs as Record<string, number> | undefined)?.X ?? 0),
          "2": Number((a.inplay_probs as Record<string, number> | undefined)?.["2"] ?? 0),
        },
        severity: (String(a.severity ?? "medium") as "critical" | "high" | "medium"),
        againstPregame: Boolean(a.against_pregame),
        againstInplay: Boolean(a.against_inplay),
        message: String(a.message ?? ""),
      }),
    ),
    betGuardrails: raw.bet_guardrails
      ? {
          enabled: Boolean(raw.bet_guardrails.enabled),
          blockNewBets: Boolean(raw.bet_guardrails.block_new_bets),
          blockNewBets2h: Boolean(raw.bet_guardrails.block_new_bets_2h),
          allow2hSuggestions: Boolean(raw.bet_guardrails.allow_2h_suggestions),
          blockMinute: Number(raw.bet_guardrails.block_minute ?? 45),
          block2hMinute: Number(raw.bet_guardrails.block_2h_minute ?? 82),
          blockReason:
            raw.bet_guardrails.block_reason != null
              ? String(raw.bet_guardrails.block_reason)
              : null,
          oneBetPerMarket: Boolean(raw.bet_guardrails.one_bet_per_market),
          pregamePalpite: raw.bet_guardrails.pregame_palpite
            ? mapOutcome(String(raw.bet_guardrails.pregame_palpite))
            : null,
          pregameProb:
            raw.bet_guardrails.pregame_prob != null
              ? Number(raw.bet_guardrails.pregame_prob)
              : null,
          inplayPalpite: raw.bet_guardrails.inplay_palpite
            ? mapOutcome(String(raw.bet_guardrails.inplay_palpite))
            : null,
          inplayProb:
            raw.bet_guardrails.inplay_prob != null
              ? Number(raw.bet_guardrails.inplay_prob)
              : null,
          htTrapWarnings: (
            (raw.bet_guardrails.ht_trap_warnings as Array<Record<string, unknown>>) ?? []
          ).map((t) => ({
            severity: String(t.severity ?? "medium"),
            code: String(t.code ?? ""),
            title: String(t.title ?? ""),
            reason: String(t.reason ?? ""),
            market: t.market != null ? String(t.market) : undefined,
            outcome: t.outcome != null ? String(t.outcome) : undefined,
            label: t.label != null ? String(t.label) : undefined,
            minute: t.minute != null ? Number(t.minute) : undefined,
            currentGoals: t.current_goals != null ? Number(t.current_goals) : undefined,
            line: t.line != null ? Number(t.line) : undefined,
          })),
          betBuilderRules: (
            (raw.bet_guardrails.bet_builder_rules as string[]) ?? []
          ).map(String),
        }
      : null,
    liveStats: mapLiveStats(raw.live_stats as Record<string, unknown> | null),
    scorealarm: mapScorealarm(raw.scorealarm as Record<string, unknown> | null),
    trendReport: mapTrendReport(raw.trend_report as Record<string, unknown> | null),
    halfTickets: mapHalfTickets(raw.half_tickets as Record<string, unknown> | null),
    viable2hMarkets: mapViable2hMarkets(raw.viable_2h_markets as Record<string, unknown> | null),
    superMultipla: raw.super_multipla
      ? {
          minLegOddForBonus: Number(
            (raw.super_multipla as Record<string, unknown>).min_leg_odd_for_bonus ?? 1.35,
          ),
          bonusPct: Number((raw.super_multipla as Record<string, unknown>).bonus_pct ?? 0.05),
          defaultStake: Number(
            (raw.super_multipla as Record<string, unknown>).default_stake ?? 10,
          ),
          suggestedCombos: (
            ((raw.super_multipla as Record<string, unknown>).suggested_combos as Array<
              Record<string, unknown>
            >) ?? []
          ).map((combo) => ({
            id: String(combo.id ?? ""),
            stake: Number(combo.stake ?? 0),
            combinedOdd: Number(combo.combined_odd ?? 0),
            productOdd:
              combo.product_odd != null ? Number(combo.product_odd) : undefined,
            pricingMode:
              combo.pricing_mode != null ? String(combo.pricing_mode) : undefined,
            combinedProb: Number(combo.combined_prob ?? 0),
            combinedEv: combo.combined_ev != null ? Number(combo.combined_ev) : null,
            potentialPayout: Number(combo.potential_payout ?? 0),
            bonusEligible: Boolean(combo.bonus_eligible),
            bonusPercentage: Number(combo.bonus_percentage ?? 0),
            finalPayout: Number(combo.final_payout ?? 0),
            warnings: ((combo.warnings as string[]) ?? []).map(String),
            legs: (
              (combo.legs as Array<Record<string, unknown>>) ?? []
            ).map((leg) => ({
              id: leg.id != null ? String(leg.id) : undefined,
              market: String(leg.market ?? ""),
              outcome: String(leg.outcome ?? ""),
              label: String(leg.label ?? leg.selection_label ?? ""),
              marketOdd: Number(leg.market_odd ?? 0),
              modelProb: Number(leg.model_prob ?? 0),
              expectedValue:
                leg.expected_value != null ? Number(leg.expected_value) : undefined,
              edgePp: leg.edge_pp != null ? Number(leg.edge_pp) : undefined,
            })),
          })),
        }
      : null,
    matchContext: (raw.match_context as Record<string, unknown> | null | undefined) ?? null,
    optimizedTickets: mapOptimizedTickets(raw.optimized_tickets as Record<string, unknown> | null | undefined),
  };
}

export function mapSuperbetLiveFeed(raw: ApiSuperbetLiveFeed) {
  return {
    count: raw.count,
    sportId: raw.sport_id,
    capturedAt: raw.captured_at,
    events: raw.events.map((event) => ({
      eventId: event.event_id,
      homeTeam: event.home_team,
      awayTeam: event.away_team,
      eventName: event.event_name,
      sportId: event.sport_id,
      tournamentId: event.tournament_id,
      utcDate: event.utc_date,
      betradarId: event.betradar_id,
      minute: event.minute,
      homeScore: event.home_score,
      awayScore: event.away_score,
      periodLabel: event.period_label,
      status: event.status,
      marketCount: event.market_count,
      h2hOdds: event.h2h_odds,
      capturedAt: event.captured_at,
      betRankScore: event.bet_rank_score ?? null,
      betTier: (event.bet_tier as SuperbetLiveEvent["betTier"]) ?? null,
      betLabel: event.bet_label ?? null,
      betPalpite: event.bet_palpite ?? null,
      betOpportunityCount: event.bet_opportunity_count ?? null,
      betTopEv: event.bet_top_ev ?? null,
      betTopLabel: event.bet_top_label ?? null,
    })),
  };
}

interface ApiSuperbetEvent {
  event_id: number;
  home_team: string;
  away_team: string;
  is_live: boolean;
  inplay: {
    home_score?: number;
    away_score?: number;
    minute?: number;
    period_label?: string | null;
    status?: string | null;
  } | null;
  h2h_odds: Record<string, number>;
  raw_market_count: number;
  captured_at: string;
}

export function mapSuperbetEvent(raw: ApiSuperbetEvent) {
  const inplay = raw.inplay;
  const homeScore = inplay?.home_score ?? 0;
  const awayScore = inplay?.away_score ?? 0;
  return {
    eventId: raw.event_id,
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    isLive: raw.is_live,
    currentScore: inplay ? `${homeScore}x${awayScore}` : null,
    minute: inplay?.minute ?? 0,
    periodLabel: inplay?.period_label ?? null,
    status: inplay?.status ?? null,
    h2hOdds: raw.h2h_odds ?? {},
    rawMarketCount: raw.raw_market_count ?? 0,
    capturedAt: raw.captured_at,
  };
}

function mapRefereeProfile(raw: Record<string, unknown>): RefereeProfile {
  return {
    name: String(raw.name ?? ""),
    country: raw.country != null ? String(raw.country) : null,
    cardLambda: Number(raw.card_lambda ?? 0),
    foulLambda: Number(raw.foul_lambda ?? 0),
    penaltyLambda: Number(raw.penalty_lambda ?? 0),
    redCardLambda: Number(raw.red_card_lambda ?? 0),
    classification: (String(raw.classification ?? "equilibrado") as
      | "punitivista"
      | "equilibrado"
      | "pacificador"),
    classificationPt: String(raw.classification_pt ?? "Equilibrado"),
    cardFoulRatio: Number(raw.card_foul_ratio ?? 0),
    avgCardsPerGame: Number(raw.avg_cards_per_game ?? 0),
    avgFoulsPerGame: Number(raw.avg_fouls_per_game ?? 0),
  };
}

function mapRefereeMarketLine(raw: Record<string, unknown>): RefereeMarketLine {
  return {
    line: Number(raw.line ?? 0),
    overProb: Number(raw.over_prob ?? 0),
    underProb: Number(raw.under_prob ?? 0),
    overOddsFair: Number(raw.over_odds_fair ?? 0),
    underOddsFair: Number(raw.under_odds_fair ?? 0),
    expectedTotal: Number(raw.expected_total ?? 0),
    recommendation: (String(raw.recommendation ?? "neutro") as "over" | "under" | "neutro"),
    confidence: (String(raw.confidence ?? "media") as "alta" | "media" | "baixa"),
    edge: raw.edge != null ? Number(raw.edge) : null,
  };
}

function mapRefereeMarkets(raw: Record<string, unknown>): RefereeMarkets {
  const yellowRaw = (raw.yellow_cards as Record<string, unknown>) ?? {};
  const redRaw = (raw.red_cards as Record<string, unknown>) ?? {};
  const penaltyRaw = (raw.penalties as Record<string, unknown>) ?? {};
  const foulsRaw = (raw.fouls as Record<string, unknown>) ?? {};
  const metaRaw = (yellowRaw.metadata as Record<string, unknown>) ?? {};

  return {
    yellowCards: {
      current: Number(yellowRaw.current ?? 0),
      expectedRemaining: Number(yellowRaw.expected_remaining ?? 0),
      expectedTotal: Number(yellowRaw.expected_total ?? 0),
      overLines: (
        (yellowRaw.over_lines as Array<Record<string, unknown>>) ?? []
      ).map(mapRefereeMarketLine),
      metadata: {
        refereeName: String(metaRaw.referee_name ?? ""),
        classification: String(metaRaw.classification ?? ""),
        classificationPt: String(metaRaw.classification_pt ?? ""),
        cardLambda: Number(metaRaw.card_lambda ?? 0),
        minute: Number(metaRaw.minute ?? 0),
        remainingMinutes: Number(metaRaw.remaining_minutes ?? 90),
      },
    },
    redCards: {
      yesProb: Number(redRaw.yes_prob ?? 0),
      yesOddsFair: Number(redRaw.yes_odds_fair ?? 0),
      recommendation: (String(redRaw.recommendation ?? "neutro") as "sim" | "nao" | "neutro"),
      confidence: String(redRaw.confidence ?? ""),
    },
    penalties: {
      yesProb: Number(penaltyRaw.yes_prob ?? 0),
      yesOddsFair: Number(penaltyRaw.yes_odds_fair ?? 0),
      recommendation: (String(penaltyRaw.recommendation ?? "neutro") as "sim" | "nao" | "neutro"),
      confidence: String(penaltyRaw.confidence ?? ""),
    },
    fouls: {
      expectedTotal: Number(foulsRaw.expected_total ?? 0),
      overLines: (
        (foulsRaw.over_lines as Array<Record<string, unknown>>) ?? []
      ).map(mapRefereeMarketLine),
    },
  };
}

export { mapWcPrediction };

export function mapUserOpenBets(raw: {
  count: number;
  bets: Array<{
    id: string;
    event_name: string;
    home_team: string;
    away_team: string;
    picks: Array<{ market: string; outcome: string; target_value?: string | null }>;
    stake: number;
    odds_placed: number;
    potential_return?: number;
    cashout_value?: number | null;
    ticket_code?: string | null;
    status: string;
    source: string;
    captured_at: string | null;
    superbet_event_id?: number | null;
    user_id?: string | null;
    bonus_eligible?: boolean | null;
    bonus_percentage?: number | null;
    final_payout?: number | null;
  }>;
}) {
  return {
    count: raw.count,
    bets: raw.bets.map((b) => ({
      id: b.id,
      eventName: b.event_name,
      homeTeam: b.home_team,
      awayTeam: b.away_team,
      picks: b.picks.map((p) => ({
        market: p.market,
        outcome: p.outcome,
        targetValue: p.target_value ?? null,
      })),
      stake: b.stake,
      oddsPlaced: b.odds_placed,
      potentialReturn: b.potential_return != null ? b.potential_return : b.stake * b.odds_placed,
      cashoutValue: b.cashout_value ?? null,
      ticketCode: b.ticket_code ?? null,
      status: b.status,
      source: b.source,
      capturedAt: b.captured_at,
      superbetEventId: b.superbet_event_id ?? null,
      userId: b.user_id ?? null,
      bonusEligible: b.bonus_eligible ?? null,
      bonusPercentage: b.bonus_percentage ?? null,
      finalPayout: b.final_payout ?? null,
    })),
  };
}

interface ApiBasketSuperbetLiveFeed {
  count: number;
  sport_id: number | null;
  captured_at: string;
  events: Array<{
    event_id: number;
    home_team: string;
    away_team: string;
    event_name: string;
    sport_id: number;
    tournament_id: number | null;
    utc_date: string | null;
    betradar_id: string | null;
    minute: number;
    home_score: number;
    away_score: number;
    period_label: string | null;
    status: string | null;
    market_count: number;
    h2h_odds: Record<string, number>;
    captured_at: string;
  }>;
}

export function mapBasketSuperbetLiveFeed(raw: ApiBasketSuperbetLiveFeed): BasketSuperbetLiveFeed {
  return {
    count: raw.count,
    sportId: raw.sport_id,
    capturedAt: raw.captured_at,
    events: raw.events.map((event) => ({
      eventId: event.event_id,
      homeTeam: event.home_team,
      awayTeam: event.away_team,
      eventName: event.event_name,
      sportId: event.sport_id,
      tournamentId: event.tournament_id,
      utcDate: event.utc_date,
      betradarId: event.betradar_id,
      minute: event.minute,
      homeScore: event.home_score,
      awayScore: event.away_score,
      periodLabel: event.period_label,
      status: event.status,
      marketCount: event.market_count,
      h2hOdds: event.h2h_odds ?? {},
      capturedAt: event.captured_at,
    })),
  };
}

interface ApiBasketSuperbetLiveAdvice {
  home_team: string;
  away_team: string;
  minute: number;
  current_score: string | null;
  period_label: string | null;
  status: string | null;
  basket_periods?: Array<{ num: number; home: number; away: number }>;
  is_finished: boolean;
  is_live: boolean;
  superbet_stale: boolean;
  superbet_event_id: number;
  sport_id: number | null;
  captured_at: string;
  h2h_odds: Record<string, number>;
  h2h_implied: Record<string, number>;
  spread_odds: Record<string, Record<string, number>>;
  spread_implied: Record<string, Record<string, number>>;
  total_points_odds: Record<string, Record<string, number>>;
  total_points_implied: Record<string, Record<string, number>>;
  inplay_summary: {
    prob_home_win?: number | null;
    prob_away_win?: number | null;
    expected_final_home?: number | null;
    expected_final_away?: number | null;
    expected_total?: number | null;
    remaining_minutes?: number | null;
    moneyline_probs?: Record<string, number>;
    spread_probs?: Record<string, number>;
    total_probs?: Record<string, number>;
    ppm_home?: number | null;
    ppm_away?: number | null;
    ppm_home_prior?: number | null;
    ppm_away_prior?: number | null;
    match_minutes?: number | null;
    n_simulations?: number | null;
    market_total_line?: number | null;
    market_spread_line?: number | null;
    next_quarter_number?: number | null;
    next_quarter_projection_home?: number | null;
    next_quarter_projection_away?: number | null;
  };
  aportes: Array<{
    market: string;
    outcome: string;
    label: string;
    model_prob: number;
    market_odd: number;
    implied_prob: number;
    expected_value: number;
    edge_pp: number;
    kelly_quarter: number;
    suggested_stake_pct: number;
    suggested_stake_value?: number | null;
    action: string;
  }>;
  confidence: { score: number; label: string; max_edge_pp: number } | null;
}

export function mapBasketSuperbetLiveAdvice(
  raw: ApiBasketSuperbetLiveAdvice,
): BasketSuperbetLiveAdvice {
  const summary = raw.inplay_summary ?? {};
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    minute: raw.minute,
    currentScore: raw.current_score,
    periodLabel: raw.period_label,
    status: raw.status,
    basketPeriods: (raw.basket_periods ?? []).map((p) => ({
      num: p.num,
      home: p.home,
      away: p.away,
    })),
    isFinished: raw.is_finished,
    isLive: raw.is_live,
    superbetStale: raw.superbet_stale,
    superbetEventId: raw.superbet_event_id,
    sportId: raw.sport_id ?? null,
    capturedAt: raw.captured_at ?? null,
    h2hOdds: raw.h2h_odds ?? {},
    h2hImplied: raw.h2h_implied ?? {},
    spreadOdds: raw.spread_odds ?? {},
    spreadImplied: raw.spread_implied ?? {},
    totalPointsOdds: raw.total_points_odds ?? {},
    totalPointsImplied: raw.total_points_implied ?? {},
    inplaySummary: {
      probHomeWin: summary.prob_home_win ?? null,
      probAwayWin: summary.prob_away_win ?? null,
      expectedFinalHome: summary.expected_final_home ?? null,
      expectedFinalAway: summary.expected_final_away ?? null,
      expectedTotal: summary.expected_total ?? null,
      remainingMinutes: summary.remaining_minutes ?? null,
      moneylineProbs: summary.moneyline_probs ?? {},
      spreadProbs: summary.spread_probs ?? {},
      totalProbs: summary.total_probs ?? {},
      ppmHome: summary.ppm_home ?? null,
      ppmAway: summary.ppm_away ?? null,
      ppmHomePrior: summary.ppm_home_prior ?? null,
      ppmAwayPrior: summary.ppm_away_prior ?? null,
      matchMinutes: summary.match_minutes ?? null,
      nSimulations: summary.n_simulations ?? null,
      marketTotalLine: summary.market_total_line ?? null,
      marketSpreadLine: summary.market_spread_line ?? null,
      nextQuarterNumber: summary.next_quarter_number ?? null,
      nextQuarterProjectionHome: summary.next_quarter_projection_home ?? null,
      nextQuarterProjectionAway: summary.next_quarter_projection_away ?? null,
    },
    aportes: (raw.aportes ?? []).map((a) => ({
      market: a.market,
      outcome: a.outcome,
      label: a.label,
      modelProb: a.model_prob,
      marketOdd: a.market_odd,
      impliedProb: a.implied_prob,
      expectedValue: a.expected_value,
      edgePp: a.edge_pp,
      kellyQuarter: a.kelly_quarter,
      suggestedStakePct: a.suggested_stake_pct,
      suggestedStakeValue: a.suggested_stake_value ?? null,
      action: a.action,
    })),
    confidence: raw.confidence
      ? {
          score: raw.confidence.score,
          label: raw.confidence.label,
          maxEdgePp: raw.confidence.max_edge_pp,
        }
      : null,
  };
}

export const mapBaseballSuperbetLiveFeed = mapBasketSuperbetLiveFeed;

interface ApiBaseballSuperbetLiveAdvice {
  home_team: string;
  away_team: string;
  inning: number;
  minute: number;
  current_score: string | null;
  period_label: string | null;
  status: string | null;
  baseball_innings?: Array<{ num: number; home: number; away: number }>;
  is_finished: boolean;
  is_live: boolean;
  superbet_stale: boolean;
  superbet_event_id: number;
  sport_id: number | null;
  captured_at: string;
  h2h_odds: Record<string, number>;
  h2h_implied: Record<string, number>;
  spread_odds: Record<string, Record<string, number>>;
  spread_implied: Record<string, Record<string, number>>;
  total_runs_odds: Record<string, Record<string, number>>;
  total_runs_implied: Record<string, Record<string, number>>;
  inplay_summary: {
    prob_home_win?: number | null;
    prob_away_win?: number | null;
    expected_final_home?: number | null;
    expected_final_away?: number | null;
    expected_total?: number | null;
    remaining_innings?: number | null;
    moneyline_probs?: Record<string, number>;
    spread_probs?: Record<string, number>;
    total_probs?: Record<string, number>;
    rpi_home?: number | null;
    rpi_away?: number | null;
    rpi_home_prior?: number | null;
    rpi_away_prior?: number | null;
    match_innings?: number | null;
    n_simulations?: number | null;
    market_total_line?: number | null;
    market_spread_line?: number | null;
  };
  aportes: ApiBasketSuperbetLiveAdvice["aportes"];
  confidence: { score: number; label: string; max_edge_pp: number } | null;
}

export function mapBaseballSuperbetLiveAdvice(
  raw: ApiBaseballSuperbetLiveAdvice,
): import("@/domain/entities").BaseballSuperbetLiveAdvice {
  const summary = raw.inplay_summary ?? {};
  return {
    homeTeam: raw.home_team,
    awayTeam: raw.away_team,
    inning: raw.inning,
    minute: raw.minute,
    currentScore: raw.current_score,
    periodLabel: raw.period_label,
    status: raw.status,
    baseballInnings: (raw.baseball_innings ?? []).map((p) => ({
      num: p.num,
      home: p.home,
      away: p.away,
    })),
    isFinished: raw.is_finished,
    isLive: raw.is_live,
    superbetStale: raw.superbet_stale,
    superbetEventId: raw.superbet_event_id,
    sportId: raw.sport_id ?? null,
    capturedAt: raw.captured_at ?? null,
    h2hOdds: raw.h2h_odds ?? {},
    h2hImplied: raw.h2h_implied ?? {},
    spreadOdds: raw.spread_odds ?? {},
    spreadImplied: raw.spread_implied ?? {},
    totalRunsOdds: raw.total_runs_odds ?? {},
    totalRunsImplied: raw.total_runs_implied ?? {},
    inplaySummary: {
      probHomeWin: summary.prob_home_win ?? null,
      probAwayWin: summary.prob_away_win ?? null,
      expectedFinalHome: summary.expected_final_home ?? null,
      expectedFinalAway: summary.expected_final_away ?? null,
      expectedTotal: summary.expected_total ?? null,
      remainingInnings: summary.remaining_innings ?? null,
      moneylineProbs: summary.moneyline_probs ?? {},
      spreadProbs: summary.spread_probs ?? {},
      totalProbs: summary.total_probs ?? {},
      rpiHome: summary.rpi_home ?? null,
      rpiAway: summary.rpi_away ?? null,
      rpiHomePrior: summary.rpi_home_prior ?? null,
      rpiAwayPrior: summary.rpi_away_prior ?? null,
      matchInnings: summary.match_innings ?? null,
      nSimulations: summary.n_simulations ?? null,
      marketTotalLine: summary.market_total_line ?? null,
      marketSpreadLine: summary.market_spread_line ?? null,
    },
    aportes: (raw.aportes ?? []).map((a) => ({
      market: a.market,
      outcome: a.outcome,
      label: a.label,
      modelProb: a.model_prob,
      marketOdd: a.market_odd,
      impliedProb: a.implied_prob,
      expectedValue: a.expected_value,
      edgePp: a.edge_pp,
      kellyQuarter: a.kelly_quarter,
      suggestedStakePct: a.suggested_stake_pct,
      suggestedStakeValue: a.suggested_stake_value ?? null,
      action: a.action,
    })),
    confidence: raw.confidence
      ? {
          score: raw.confidence.score,
          label: raw.confidence.label,
          maxEdgePp: raw.confidence.max_edge_pp,
        }
      : null,
  };
}

type ApiLiveCopilot = {
  enabled: boolean;
  available: boolean;
  sport: string;
  event_id: number;
  captured_at?: string | null;
  cached?: boolean;
  model?: string | null;
  error?: string | null;
  wait_reason?: string | null;
  momento?: string;
  acao_agora?: string;
  confianca_geral?: string;
  picks?: Array<{
    rank: number;
    market: string;
    outcome: string;
    label: string;
    rationale: string;
    confidence: string;
    model_prob?: number | null;
    market_odd?: number | null;
    expected_value?: number | null;
    edge_pp?: number | null;
    suggested_stake_pct?: number | null;
  }>;
  alertas?: string[];
  bilhete?: {
    tipo?: string;
    titulo?: string;
    resumo?: string;
    valid?: boolean;
    combined_odd?: number | null;
    combined_odd_simple?: number | null;
    pricing_mode?: string | null;
    avisos_correlacao?: string[];
    validation_warnings?: string[];
    pernas?: Array<{
      rank: number;
      market: string;
      outcome: string;
      label: string;
      papel?: string;
      rationale?: string;
      market_odd?: number | null;
      model_prob?: number | null;
      expected_value?: number | null;
      edge_pp?: number | null;
    }>;
  } | null;
};

function parseCopilotAction(value: string | undefined): "apostar" | "aguardar" | "cashout" {
  const acao = String(value ?? "aguardar").toLowerCase();
  if (acao === "apostar" || acao === "cashout") return acao;
  return "aguardar";
}

function mapCopilotBilhete(raw: ApiLiveCopilot["bilhete"]) {
  if (!raw) return null;
  return {
    tipo: raw.tipo ?? "nenhum",
    titulo: raw.titulo ?? "",
    resumo: raw.resumo ?? "",
    pernas: (raw.pernas ?? []).map((p) => ({
      rank: p.rank,
      market: p.market,
      outcome: p.outcome,
      label: p.label,
      papel: p.papel ?? "complemento",
      rationale: p.rationale ?? "",
      marketOdd: p.market_odd ?? null,
      modelProb: p.model_prob ?? null,
      expectedValue: p.expected_value ?? null,
      edgePp: p.edge_pp ?? null,
    })),
    valid: Boolean(raw.valid),
    combinedOdd: raw.combined_odd ?? null,
    combinedOddSimple: raw.combined_odd_simple ?? null,
    pricingMode: raw.pricing_mode ?? null,
    avisosCorrelacao: raw.avisos_correlacao ?? [],
    validationWarnings: raw.validation_warnings ?? [],
  };
}

export function mapLiveCopilot(raw: ApiLiveCopilot) {
  return {
    enabled: Boolean(raw.enabled),
    available: Boolean(raw.available),
    sport: raw.sport,
    eventId: raw.event_id,
    capturedAt: raw.captured_at ?? null,
    cached: Boolean(raw.cached),
    model: raw.model ?? null,
    error: raw.error ?? null,
    waitReason: raw.wait_reason ?? null,
    momento: raw.momento ?? "",
    acaoAgora: parseCopilotAction(raw.acao_agora),
    confiancaGeral: raw.confianca_geral ?? "Baixa",
    picks: (raw.picks ?? []).map((p) => ({
      rank: p.rank,
      market: p.market,
      outcome: p.outcome,
      label: p.label,
      rationale: p.rationale,
      confidence: p.confidence,
      modelProb: p.model_prob ?? null,
      marketOdd: p.market_odd ?? null,
      expectedValue: p.expected_value ?? null,
      edgePp: p.edge_pp ?? null,
      suggestedStakePct: p.suggested_stake_pct ?? null,
    })),
    alertas: raw.alertas ?? [],
    bilhete: mapCopilotBilhete(raw.bilhete),
  };
}

function mapCopilotUiLeg(raw: Record<string, unknown>): LiveCopilotUiLeg {
  return {
    market: String(raw.market ?? ""),
    outcome: String(raw.outcome ?? ""),
    label: String(raw.label ?? ""),
    modelProb: raw.model_prob != null ? Number(raw.model_prob) : null,
    marketOdd: raw.market_odd != null ? Number(raw.market_odd) : null,
    expectedValue: raw.expected_value != null ? Number(raw.expected_value) : null,
    edgePp: raw.edge_pp != null ? Number(raw.edge_pp) : null,
    suggestedStakePct: raw.suggested_stake_pct != null ? Number(raw.suggested_stake_pct) : null,
  };
}

function mapCopilotUiAction(raw: Record<string, unknown>): LiveCopilotUiAction {
  const legsRaw = Array.isArray(raw.legs) ? raw.legs : [];
  return {
    type: (raw.type as LiveCopilotUiAction["type"]) ?? "notify",
    title: raw.title != null ? String(raw.title) : null,
    body: raw.body != null ? String(raw.body) : null,
    tab: raw.tab != null ? (String(raw.tab) as LiveCopilotTabId) : null,
    legs: legsRaw.map((leg) => mapCopilotUiLeg(leg as Record<string, unknown>)),
  };
}

export function mapLiveCopilotAgent(raw: Record<string, unknown>): LiveCopilotAgent {
  const base = mapLiveCopilot(raw as Parameters<typeof mapLiveCopilot>[0]);
  const actionsRaw = Array.isArray(raw.ui_actions) ? raw.ui_actions : [];
  const toolsRaw = Array.isArray(raw.tools_used) ? raw.tools_used : [];
  return {
    ...base,
    mode: String(raw.mode ?? "agent"),
    reply: String(raw.reply ?? ""),
    toolsUsed: toolsRaw.map(String),
    uiActions: actionsRaw.map((a) => mapCopilotUiAction(a as Record<string, unknown>)),
    autoApplyUi: Boolean(raw.auto_apply_ui),
  };
}
