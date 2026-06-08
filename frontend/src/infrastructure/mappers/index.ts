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
}

interface ApiWcSchedule {
  season: number;
  competition: string;
  phase: string;
  groups: { id: string; teams: string[] }[];
  matchdays: number[];
  matches: ApiWcScheduleMatch[];
  total_matches: number;
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
    }[];
  }[];
}): WcGroupStandings {
  return {
    season: raw.season,
    competition: raw.competition,
    simulated: raw.simulated,
    note: raw.note,
    groups: raw.groups.map((g) => ({
      group: g.group,
      standings: g.standings.map((r) => ({ ...r })),
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
  inplay_summary: Record<string, number>;
  btts_odds?: Record<string, number>;
  next_goal_odds?: Record<string, number>;
  analysis_coverage?: {
    h2h?: boolean;
    totals?: boolean;
    btts?: boolean;
    next_goal?: boolean;
    combos?: string[];
  } | null;
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
      expectedValue: Number(op.expected_value),
      edgePp: Number(op.edge_pp),
      suggestedStakePct: Number(op.suggested_stake_pct),
      suggestedStakeValue: Number(op.suggested_stake_value),
      action: String(op.action),
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
    superbetEventId: raw.superbet_event_id,
    betradarId: raw.betradar_id,
    capturedAt: raw.captured_at,
    rawMarketCount: raw.raw_market_count,
    h2hOdds: raw.h2h_odds ?? {},
    h2hImplied: raw.h2h_implied ?? {},
    h2hOverround: raw.h2h_overround ?? null,
    generosityProbs: raw.generosity_probs ?? {},
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
      over25: summary.over_2_5,
      btts: summary.btts,
      probNextGoalHome: summary.prob_next_goal_home,
      probNextGoalAway: summary.prob_next_goal_away,
      probNoMoreGoals: summary.prob_no_more_goals,
    },
    bttsOdds: raw.btts_odds ?? {},
    nextGoalOdds: raw.next_goal_odds ?? {},
    analysisCoverage: raw.analysis_coverage
      ? {
          h2h: Boolean(raw.analysis_coverage.h2h),
          totals: Boolean(raw.analysis_coverage.totals),
          btts: Boolean(raw.analysis_coverage.btts),
          nextGoal: Boolean(raw.analysis_coverage.next_goal),
          combos: ((raw.analysis_coverage.combos as string[]) ?? []).map(String),
        }
      : null,
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
    })),
  };
}

export { mapWcPrediction };
