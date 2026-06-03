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

export interface HealthStatus {
  status: string;
  articlesSilver: number;
  fixtures: number;
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
