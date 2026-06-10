export type OutcomeLabel = "1" | "X" | "2";

export interface GoalModelFactors {
  leagueAvg: number;
  homeAttack: number;
  awayAttack: number;
  homeDefense: number;
  awayDefense: number;
  homeAdvantage: number;
  eloFactorHome: number;
  eloFactorAway: number;
  lambdaHome: number;
  lambdaAway: number;
  rho: number;
}

export interface CornerModelFactors {
  leagueAvg: number;
  homeAttack: number;
  awayAttack: number;
  homeDefense: number;
  awayDefense: number;
  homeAdvantage: number;
  eloFactorHome: number;
  eloFactorAway: number;
  lambdaHome: number;
  lambdaAway: number;
  trainingMatches: number;
  blendWithGoalProxy: number;
}

export interface CornersTrainingSummary {
  matches: number;
  teams: number;
  avgHomeCorners: number | null;
  avgAwayCorners: number | null;
  avgTotalCorners: number | null;
}

export interface WcCornersPrediction {
  homeTeam: string;
  awayTeam: string;
  dataSource: string;
  expectedCorners: string;
  expectedTotalCorners: number;
  mostLikelyCorners: string;
  probHomeMoreCorners: number;
  probDrawCorners: number;
  probAwayMoreCorners: number;
  lineProbs: Record<string, number>;
  factors: CornerModelFactors;
  trainingSummary: CornersTrainingSummary;
}

export interface KxlSectorScore {
  setor: string;
  colisao: number;
  attackDna?: number;
  permissividade?: number;
}

export interface KxlLethalityMethod {
  metodo: string;
  ataquePct: number;
  gkFracoPct: number;
  pressao: number;
}

export interface KxlLethalityBreakdown {
  dominant: string;
  index: number;
  eacp: number;
  metodos: KxlLethalityMethod[];
}

export interface KxlCollisionSide {
  energia: number;
  espaco: number;
  tempo: number;
  vcarRaw: number;
  vesc: number;
  vEff: number;
  setores: KxlSectorScore[];
  lethalityGk: KxlLethalityBreakdown | null;
}

export interface KxlCollisionBreakdown {
  probHome: number;
  probDraw: number;
  probAway: number;
  vDelta: number;
  sectorNote: string;
  lethalityNote: string;
  home: KxlCollisionSide;
  away: KxlCollisionSide;
  notes: string[];
}

/** Snapshot dos índices KXL calculados a partir do baseline real da seleção. */
export interface KxlTeamSnapshot {
  /** Índice de ataque calculado (Dixon-Coles normalizado) */
  attackIndex: number;
  /** Índice de defesa calculado */
  defenseIndex: number;
  /** Índice de controle de jogo (posse × passes × dribles) */
  controlIndex: number;
  /** Índice do goleiro */
  gkIndex: number;
  /** Fator de caos/imprevisibilidade (FSC) */
  chaos: number;
  /** Chutes totais por jogo (ECCH) */
  shotsPerGame: number;
  /** Posse de bola média em % (ECPB, 0-100) */
  possessionPct: number;
  /** Gols de contra-ataque por jogo (EACA) */
  counterAttack: number;
  /** % de gols marcados dentro da área (EAGD) */
  insideGoalPct: number;
  /** % de gols sofridos dentro da área — fraqueza do GK (EGSD) */
  gkInsideWeaknessPct: number;
}

export interface KxlBaselineBreakdown {
  probHome: number;
  probDraw: number;
  probAway: number;
  sectorNote: string;
  homeEdge: number;
  awayEdge: number;
  homeAttackVsAwayDef: number;
  awayAttackVsHomeDef: number;
  homeSnapshot: KxlTeamSnapshot | null;
  awaySnapshot: KxlTeamSnapshot | null;
}

export interface KxlFeptPlayer {
  name: string;
  position: string | null;
  line: string | null;
  sofascoreRating: number | null;
}

export interface KxlFeptMeta {
  source: string;
  eventId: number;
  ratingsFound: number;
  ratingsMissing: number;
  esquemaMandante: string | null;
  esquemaVisitante: string | null;
  homePlayers?: KxlFeptPlayer[];
  awayPlayers?: KxlFeptPlayer[];
  absencesHome?: number;
  absencesAway?: number;
  referee?: string | null;
  refereeProfile?: string | null;
  refereeCardsPerGame?: number | null;
  autoMerged: boolean;
  note?: string | null;
}

export interface SofascoreResolvedEvent {
  eventId: number;
  homeTeam: string;
  awayTeam: string;
  matchDate: string;
  sofascoreHome: string | null;
  sofascoreAway: string | null;
}

export interface WcInPlayPrediction {
  homeTeam: string;
  awayTeam: string;
  currentScore: string;
  minute: number;
  matchMinutes: number;
  remainingFraction: number;
  lambdaFullHome: number;
  lambdaFullAway: number;
  lambdaRemainingHome: number;
  lambdaRemainingAway: number;
  rhoUsed: number;
  probFinalHome: number;
  probFinalDraw: number;
  probFinalAway: number;
  probHtHome: number;
  probHtDraw: number;
  probHtAway: number;
  probNoMoreGoals: number;
  probNextGoalHome: number;
  probNextGoalAway: number;
  finalLineProbs: Record<string, number>;
  remainderLineProbs: Record<string, number>;
  htLineProbs: Record<string, number>;
  secondHalfLineProbs: Record<string, number>;
  teamFinalLineProbs: Record<string, number>;
  topFinalScores: Record<string, number>;
  topHtFt: Record<string, number>;
  comboMarkets: Record<string, number>;
  bttsFinal: number;
  nSimulations: number;
  marketBenchmark: {
    h2h?: Record<string, { market: number; model: number; edge: number; odds?: number }>;
    totals?: Record<string, { marketOver: number; modelOver: number; edgeOver: number }>;
  } | null;
}

export interface MonteCarloBreakdown {
  probHome: number;
  probDraw: number;
  probAway: number;
  expectedGoalsHome: number;
  expectedGoalsAway: number;
  over25: number;
  under25: number;
  bothTeamsScore: number;
  cleanSheetHome: number;
  cleanSheetAway: number;
  topScores: Record<string, number>;
  nSimulations: number;
  rhoUsed: number;
}

export interface ModelBreakdown {
  dixonColes: Record<OutcomeLabel, number>;
  logistic: Record<OutcomeLabel, number>;
  dixonColesRho: number | null;
  poissonFactors: GoalModelFactors | null;
  holdout2022Accuracy: number | null;
  ensembleWeights: { dixonColes: number; logistic: number };
  ensembleBrier: number | null;
  kxlBaseline: KxlBaselineBreakdown | null;
  kxlCollision: KxlCollisionBreakdown | null;
  kxlFept: KxlFeptMeta | null;
  monteCarlo: MonteCarloBreakdown | null;
}

export interface PreMatchTeamStats {
  elo: number;
  goalsPerGame: number;
  concededPerGame: number;
  form: string;
}

export interface MatchContextView {
  preMatch: {
    home: PreMatchTeamStats;
    away: PreMatchTeamStats;
    h2h: { homeWins: number; draws: number; awayWins: number; total: number };
  } | null;
  kxlProfile: {
    home: { attack: number; defense: number; control: number; shots?: number; possession?: number; counter?: number; gkWeakness?: number };
    away: { attack: number; defense: number; control: number; shots?: number; possession?: number; gkWeakness?: number };
    sectorNote: string;
    pressureHome: number;
    pressureAway: number;
    probHome: number;
    probDraw: number;
    probAway: number;
  } | null;
}

export interface WcPrediction {
  homeTeam: string;
  awayTeam: string;
  prediction: OutcomeLabel;
  confidence: number;
  probHome: number;
  probDraw: number;
  probAway: number;
  poissonScore: string;
  expectedGoals: string;
  context: string;
  h2hSummary: string;
  modelBreakdown: ModelBreakdown;
}

export interface WcRound {
  season: number;
  competition: string;
  phase: string;
  round: number;
  predictions: WcPrediction[];
}

export interface WcScheduleGroup {
  id: string;
  teams: string[];
}

export interface WcScheduleMatch {
  matchId: string;
  homeTeam: string;
  awayTeam: string;
  group: string | null;
  round: number;
  phase: string;
  kickoff: string | null;
  venue: string | null;
  city: string | null;
}

export interface WcSchedule {
  season: number;
  competition: string;
  phase: string;
  groups: WcScheduleGroup[];
  matchdays: number[];
  matches: WcScheduleMatch[];
  totalMatches: number;
}

export interface WcFriendlyMatch {
  eventId: number | null;
  fifaMatchId: string | null;
  sources: string[];
  homeTeam: string;
  awayTeam: string;
  matchDate: string | null;
  status: string;
  homeScore: number | null;
  awayScore: number | null;
  tournament: string;
  isHome: boolean;
}

export interface WcSimulationLineupPlayer {
  name: string;
  shirtNumber: number | null;
  position: string | null;
  line?: string | null;
  isCaptain: boolean;
  pictureUrl: string | null;
  sofascoreRating?: number | null;
  yellowCards?: number;
  redCards?: number;
  isStarter?: boolean;
}

export interface WcSimulation {
  homeTeam: string;
  awayTeam: string;
  matchDate: string | null;
  prediction: OutcomeLabel;
  confidence: number;
  probHome: number;
  probDraw: number;
  probAway: number;
  poissonScore: string | null;
  expectedGoals: string | null;
  fifaHomeLineup: WcSimulationLineupPlayer[] | null;
  fifaAwayLineup: WcSimulationLineupPlayer[] | null;
  fifaHomeBench: WcSimulationLineupPlayer[] | null;
  fifaAwayBench: WcSimulationLineupPlayer[] | null;
  fifaHomeTactics: string | null;
  fifaAwayTactics: string | null;
  fifaHomeCoach: string | null;
  fifaAwayCoach: string | null;
  fifaStadium: string | null;
  fifaHomePoints: number | null;
  fifaAwayPoints: number | null;
  fifaPointsDiff: number | null;
  lineupSource: string | null;
  warnings: string[];
}

export interface WcFriendlies {
  team: string;
  year: number;
  count: number;
  friendlies: WcFriendlyMatch[];
  source: string;
}

export interface SuperbetLiveEvent {
  eventId: number;
  homeTeam: string;
  awayTeam: string;
  eventName: string;
  sportId: number;
  tournamentId: number | null;
  utcDate: string | null;
  betradarId: string | null;
  minute: number;
  homeScore: number;
  awayScore: number;
  periodLabel: string | null;
  status: string | null;
  marketCount: number;
  h2hOdds: Record<string, number>;
  capturedAt: string;
}

export interface SuperbetLiveFeed {
  count: number;
  sportId: number | null;
  events: SuperbetLiveEvent[];
  capturedAt: string;
}

export interface SuperbetLiveAdvice {
  homeTeam: string;
  awayTeam: string;
  minute: number;
  currentScore: string | null;
  periodLabel: string | null;
  status: string | null;
  isFinished: boolean;
  isLive: boolean;
  superbetEventId: number;
  betradarId: string | null;
  capturedAt: string | null;
  rawMarketCount: number;
  h2hOdds: Record<string, number>;
  h2hImplied: Record<string, number>;
  h2hOverround: number | null;
  generosityProbs: Record<string, number>;
  confidence: {
    score: number;
    label: string;
    reason: string;
  } | null;
  marketBenchmark: {
    h2h?: Record<string, { market: number; model: number; edge: number; odds?: number }>;
    totals?: Record<string, { marketOver: number; modelOver: number; edgeOver: number }>;
  } | null;
  strategy: {
    posture: string;
    maxNewExposurePct: number;
    maxNewExposureValue: number;
    opportunityCount: number;
    strongOpportunityCount: number;
    minEdgeThreshold: number;
    waitReason: string;
    watchList: Array<{
      market: string;
      outcome: string;
      label: string;
      modelProb: number;
      marketOdd: number;
      expectedValue: number;
      edgePp: number;
      meetsThreshold: boolean;
    }>;
    marketScan: Array<{
      market: string;
      outcome: string;
      label: string;
      modelProb: number;
      marketOdd: number;
      impliedProb: number;
      expectedValue: number;
      edgePp: number;
      suggestedStakePct: number;
      suggestedStakeValue: number;
      meetsThreshold: boolean;
    }>;
    opportunities: Array<{
      rank: number;
      market: string;
      outcome: string;
      label: string;
      tier: string;
      modelProb: number;
      marketOdd: number;
      expectedValue: number;
      edgePp: number;
      suggestedStakePct: number;
      suggestedStakeValue: number;
      action: string;
    }>;
    shields: Array<{
      action: string;
      priority: string;
      title: string;
      reason: string;
      market?: string;
      outcome?: string;
      odd?: number;
      expectedValue?: number;
    }>;
    rules: string[];
    cashout: { action: string; confidence: number; reason: string } | null;
  } | null;
  cashout: {
    action: string;
    confidence: number;
    reason: string;
    currentModelProb: number;
    placedImpliedProb?: number;
    remainingEv: number;
    estimatedFairCashout: number;
    potentialReturn: number;
  } | null;
  aportes: Array<{
    label: string;
    market: string;
    outcome: string;
    modelProb: number;
    marketOdd: number;
    expectedValue: number;
    edgePp: number;
    suggestedStakePct: number;
    suggestedStakeValue: number;
    action: string;
  }>;
  bttsOdds: Record<string, number>;
  nextGoalOdds: Record<string, number>;
  analysisCoverage: {
    h2h: boolean;
    totals: boolean;
    btts: boolean;
    nextGoal: boolean;
    combos: string[];
  } | null;
  inplaySummary: {
    probFinalHome: number;
    probFinalDraw: number;
    probFinalAway: number;
    over25?: number;
    btts?: number;
    probNextGoalHome?: number;
    probNextGoalAway?: number;
    probNoMoreGoals?: number;
    topFinalScores?: Record<string, number>;
  };
  hedgeReport: {
    advices: Array<{
      bet_id: string;
      event_name: string;
      market: string;
      outcome: string;
      stake: number;
      odds_placed: number;
      potential_return: number;
      prob_current: number;
      ev_remaining: number;
      action: "cashout" | "hedge" | "hold" | "shift";
      urgency: "critical" | "high" | "medium" | "low";
      reasoning: string;
      hedge?: {
        market: string;
        outcome: string;
        odd_current: number;
        stake_suggested: number;
        guaranteed_return: number;
        net_if_original_wins: number;
        net_if_hedge_wins: number;
      };
      cashout_value?: number;
    }>;
    total_at_risk: number;
    total_potential: number;
    overall_action: string;
    summary: string;
  } | null;
}

export interface WcSquadPlayer {
  name: string;
  club: string | null;
}

export interface WcSquadSection {
  role: string;
  position: string;
  players: WcSquadPlayer[];
}

export interface WcSquad {
  team: string;
  playerCount: number;
  sections: WcSquadSection[];
}

export interface WcSquadTeamSummary {
  team: string;
  playerCount: number;
}

export interface WcSquadsIndex {
  season: number;
  competition: string;
  sourceUrl: string;
  updatedAt: string;
  teamCount: number;
  teams: WcSquadTeamSummary[];
}

export interface WcSquadDetail {
  season: number;
  competition: string;
  sourceUrl: string;
  updatedAt: string;
  squad: WcSquad;
}

export interface BrasileiraoPrediction {
  homeTeam: string;
  awayTeam: string;
  prediction: OutcomeLabel;
  confidence: number;
  reason: string;
  newsCount: number;
}

export interface BrasileiraoRound {
  roundNumber: number;
  competition: string;
  predictions: BrasileiraoPrediction[];
}

export interface ValueOutcome {
  outcome: OutcomeLabel;
  odd: number;
  modelProb: number;
  impliedProb: number;
  expectedValue: number;
  fairOdd: number;
  kellyQuarter: number;
}

export interface ValueMatch {
  homeTeam: string;
  awayTeam: string;
  best: ValueOutcome | null;
  outcomes: ValueOutcome[];
}

export interface ValueBetsReport {
  matchedGames: number;
  totalScheduleGames: number;
  source: string;
  capturedAt: string | null;
  edges: ValueMatch[];
}

export interface WcArtifactHealth {
  holdoutAccuracy?: number | null;
  ensembleBrier?: number | null;
  ensembleWeights?: { dixon_coles?: number; logistic?: number };
  featureCount?: number;
  loadedFromCache?: boolean;
}

export interface HealthStatus {
  status: string;
  articlesSilver: number;
  fixtures: number;
  wcArtifact?: WcArtifactHealth | null;
}

export interface WcGroupStandingRow {
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
}

export interface WcGroupStandingsBlock {
  group: string;
  standings: WcGroupStandingRow[];
}

export interface WcGroupStandings {
  season: number;
  competition: string;
  simulated: boolean;
  note: string;
  groups: WcGroupStandingsBlock[];
}

export type NewsSentimentLabel = "positive" | "neutral" | "negative";

export interface NewsSource {
  id: string;
  name: string;
  count: number;
}

export interface NewsArticle {
  id: string;
  source: string;
  sourceName: string;
  sourceUrl: string;
  title: string;
  summary: string | null;
  bodyPreview: string;
  publishedAt: string | null;
  scrapedAt: string | null;
  teamsMentioned: string[];
  categories: string[];
  sentimentScore: number | null;
  sentimentLabel: NewsSentimentLabel;
}

export interface NewsFeed {
  total: number;
  limit: number;
  offset: number;
  sources: NewsSource[];
  articles: NewsArticle[];
}

export interface NewsCards {
  total: number;
  limit: number;
  offset: number;
  teams: string[];
  cards: NewsArticle[];
}

export interface NewsSyncResult {
  collected: number;
  bySource: Record<string, number>;
  silverUpdated: boolean;
  articlesSilver: number;
  syncedAt: string;
}

export interface WcEdition {
  season: number;
  label: string;
  matchCount: number;
}

export interface WcHistoricalMatch {
  matchId: string;
  season: number;
  homeTeam: string;
  awayTeam: string;
  matchDate: string;
  phase: string;
  phaseLabel: string;
  groupName: string | null;
  homeScore: number;
  awayScore: number;
  result: OutcomeLabel;
  resultLabel: string;
  score: string;
}

export interface HistoricalValidationMatch {
  matchId: string;
  season: number;
  homeTeam: string;
  awayTeam: string;
  matchDate: string;
  phase: string;
  phaseLabel: string;
  groupName: string | null;
  homeScore: number;
  awayScore: number;
  actualResult: OutcomeLabel;
  actualResultLabel: string;
  actualScore: string;
}

export interface HistoricalValidationResult {
  match: HistoricalValidationMatch;
  prediction: OutcomeLabel;
  confidence: number;
  probHome: number;
  probDraw: number;
  probAway: number;
  poissonScore: string;
  expectedGoals: string;
  correct: boolean;
  context: string;
  h2hSummary: string;
  modelBreakdown: ModelBreakdown;
  cutoffDate: string;
  cutoffNote: string;
}

export interface UserOpenBet {
  id: string;
  eventName: string;
  homeTeam: string;
  awayTeam: string;
  picks: Array<{ market: string; outcome: string; targetValue?: string | null }>;
  stake: number;
  oddsPlaced: number;
  potentialReturn: number;
  cashoutValue: number | null;
  ticketCode: string | null;
  status: string;
  source: string;
  capturedAt: string | null;
  superbetEventId?: number | null;
  userId?: string | null;
}

export interface UserOpenBetsList {
  count: number;
  bets: UserOpenBet[];
}
