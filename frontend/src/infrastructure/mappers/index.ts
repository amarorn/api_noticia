import type {
  BrasileiraoRound,
  HealthStatus,
  KxlBaselineBreakdown,
  KxlCollisionBreakdown,
  KxlLethalityBreakdown,
  KxlTeamSnapshot,
  ModelBreakdown,
  OutcomeLabel,
  ValueBetsReport,
  ValueMatch,
  ValueOutcome,
  WcPrediction,
  WcRound,
  WcSchedule,
  WcScheduleMatch,
  WcSquadDetail,
  WcSquadsIndex,
  WcGroupStandings,
  WcArtifactHealth,
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

export { mapWcPrediction };
