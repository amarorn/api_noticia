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
  handicapProbs?: Record<string, number>;
}

export interface HandicapLine {
  line: number;
  side: "home" | "away";
  modelProb: number;
  superbetOdd: number | null;
  ev: number | null;
  kellyStake: number;
  recommendation: "bet" | "avoid" | "watch" | string;
}

export interface HandicapAnalysis {
  eventId: number;
  homeTeam: string;
  awayTeam: string;
  currentScore: string;
  minute: number;
  phase: string;
  lines: HandicapLine[];
  bestBet: HandicapLine | null;
  timestamp: string;
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
  maxProbOutcome?: OutcomeLabel | null;
  maxProb?: number | null;
  probMargin?: number | null;
  uncertainty?: "alta" | "media" | "baixa" | null;
  pickReason?: "argmax" | "empate_equilibrio" | null;
  actualScore?: string | null;
  actualOutcome?: OutcomeLabel | null;
  predictionHit?: boolean | null;
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
  fifaStage?: string | null;
  homeScore?: number | null;
  awayScore?: number | null;
  played?: boolean;
  prediction?: "1" | "X" | "2" | null;
  confidence?: number | null;
  probHome?: number | null;
  probDraw?: number | null;
  probAway?: number | null;
}

export interface WcSchedulePredictionsSummary {
  loaded: number;
  distribution: Record<string, number>;
  draws: number;
}

export interface WcSchedule {
  season: number;
  competition: string;
  phase: string;
  groups: WcScheduleGroup[];
  matchdays: number[];
  matches: WcScheduleMatch[];
  totalMatches: number;
  resultsSyncedAt?: string | null;
  predictionsSummary?: WcSchedulePredictionsSummary | null;
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
  betRankScore?: number | null;
  betTier?: "top" | "good" | "watch" | "skip" | "blocked" | null;
  betLabel?: string | null;
  betPalpite?: string | null;
  betOpportunityCount?: number | null;
  betTopEv?: number | null;
  betTopLabel?: string | null;
}

export interface SuperbetLiveFeed {
  count: number;
  sportId: number | null;
  events: SuperbetLiveEvent[];
  capturedAt: string;
}

/** Snapshot leve da Superbet (placar/minuto/odds) sem rodar o modelo in-play. */
export interface SuperbetEventSnapshot {
  eventId: number;
  homeTeam: string;
  awayTeam: string;
  isLive: boolean;
  currentScore: string | null;
  minute: number;
  periodLabel: string | null;
  status: string | null;
  h2hOdds: Record<string, number>;
  rawMarketCount: number;
  capturedAt: string;
}

export interface HalftimeAdjustReport {
  applied: boolean;
  summary: string;
  frozenStats: {
    htHomeScore: number;
    htAwayScore: number;
    homeCorners1h: number;
    awayCorners1h: number;
    homeYellows1h: number;
    awayYellows1h: number;
    frozenAt: string;
  };
  goalAdjustment: {
    home2hFactor: number;
    away2hFactor: number;
    reasons: string[];
  };
  corners: {
    observed1hHome: number;
    observed1hAway: number;
    expected2hHome: number;
    expected2hAway: number;
    expectedFtTotal: number;
    probHomeMoreCorners?: number;
  };
  cards: {
    observed1hTotal: number;
    expected2hTotal: number;
    expectedFtTotal: number;
  };
  cornerLineProbs: Record<string, number>;
  cardLineProbs: Record<string, number>;
}

export interface CornersProjection {
  source: string;
  minute: number;
  observedHome: number;
  observedAway: number;
  observedTotal: number;
  expectedRemainingHome: number;
  expectedRemainingAway: number;
  expectedFtHome: number;
  expectedFtAway: number;
  expectedFtTotal: number;
  probHomeMoreCorners: number;
  probDrawCorners: number;
  probAwayMoreCorners: number;
  mostLikelyCorners: string;
  lineProbs: Record<string, number>;
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
  scoreStale?: {
    scoreStale: boolean;
    warnings: string[];
    scorealarmGoals?: number;
    snapshotGoals?: number;
  } | null;
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
    patternAccuracy?: {
      score: number;
      label: string;
      reason: string;
      homeHitRate: number | null;
      awayHitRate: number | null;
      patternCount: number;
    } | null;
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
      impliedProb?: number;
      expectedValue: number;
      edgePp: number;
      suggestedStakePct: number;
      suggestedStakeValue: number;
      action: string;
      timing?: string;
      timingReason?: string;
      fundamentacao?: string;
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
    patternAccuracy: {
      score: number;
      label: string;
      reason: string;
      homeHitRate: number | null;
      awayHitRate: number | null;
      patternCount: number;
    } | null;
    comboTicket: {
      available: boolean;
      title: string;
      reason: string | null;
      accuracy: {
        score: number;
        label: string;
        reason: string;
        homeHitRate: number | null;
        awayHitRate: number | null;
        patternCount: number;
      } | null;
      mainBets: Array<{
        rank: number;
        role: string;
        label: string;
        stat: string;
        period: string;
        direction: string;
        line: number | null;
        hitRate: number;
        hits: number;
        total: number;
        patternRef: string;
        score: number;
        availableOnBook?: boolean;
        bookChecked?: boolean;
        marketOdd: number | null;
        impliedProb?: number | null;
        expectedValue?: number | null;
        edgePp?: number | null;
        superbetMarket?: string | null;
        superbetPick?: string | null;
        lineAdjustment?: string | null;
        fairOdd?: number | null;
      }>;
      reserveBets: Array<{
        rank: number;
        role: string;
        label: string;
        stat: string;
        period: string;
        direction: string;
        line: number | null;
        hitRate: number;
        hits: number;
        total: number;
        patternRef: string;
        score: number;
        availableOnBook?: boolean;
        bookChecked?: boolean;
        marketOdd: number | null;
        impliedProb?: number | null;
        expectedValue?: number | null;
        edgePp?: number | null;
        superbetMarket?: string | null;
        superbetPick?: string | null;
        lineAdjustment?: string | null;
        fairOdd?: number | null;
      }>;
      strategyNotes: string[];
      suggestedStakePct: number;
      suggestedStakeValue: number;
      combinedHitRateEstimate: number;
      comboOdd: number | null;
      comboEv: number | null;
      superbetCapturedAt: string | null;
      bookCoverage: {
        mainAvailable: number;
        mainTotal: number;
        reserveAvailable: number;
        reserveTotal: number;
      } | null;
      last10Analysis: {
        windowSize: number;
        sourceNote: string;
        incidentsFetched: number;
        legs: Array<{
          rank: number | null;
          label: string;
          stat: string;
          period: string;
          direction: string;
          line: number | null;
          patternRef: string | null;
          kxlCrossing: { hits: number; total: number; hitRate: number | null };
          sofascoreCrossing: {
            hits: number | null;
            total: number | null;
            hitRate: number | null;
            evaluated?: number | null;
          };
          teams: Array<{
            team: string;
            hits: number;
            total: number;
            evaluated: number;
            hitRate: number | null;
            kxlPattern: {
              team: string;
              hits: number;
              total: number;
              hitRate: number | null;
              line: number | null;
              source: string;
            } | null;
            matches: Array<{
              eventId: number;
              matchDate: string | null;
              homeTeam: string;
              awayTeam: string;
              metricValue: number | null;
              hit: boolean | null;
              detail: string;
              incidentsSource: string | null;
            }>;
          }>;
        }>;
      } | null;
    } | null;
    hedgePairStrategies: {
      enabled: boolean;
      available: boolean;
      candidateCount: number;
      error: string | null;
      strategies: Array<{
        id: string;
        titulo: string;
        resumo: string;
        stakeSplit: string;
        cenarioChave: string;
        llmEnriched: boolean;
        stakeHintPct: number;
        stakeHintValue: number;
        scenarioA: string;
        scenarioB: string;
        scenarioBoth: string;
        coverage: {
          probLegA: number;
          probLegB: number;
          probBothWin: number;
          probAtLeastOne: number;
          probBothLose: number;
        };
        legA: {
          market: string;
          outcome: string;
          label: string;
          modelProb: number;
          marketOdd: number;
          expectedValue: number;
          edgePp: number;
        };
        legB: {
          market: string;
          outcome: string;
          label: string;
          modelProb: number;
          marketOdd: number;
          expectedValue: number;
          edgePp: number;
        };
      }>;
    } | null;
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
    trendInfluenced?: boolean;
    trendUrgency?: string | null;
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
    firstHalf?: boolean;
    secondHalf?: boolean;
    halftimeAdjust?: boolean;
    corners?: boolean;
    yellowCards?: boolean;
  } | null;
  halftimeReport?: HalftimeAdjustReport | null;
  cornersProjection?: CornersProjection | null;
  halfMarkets?: Record<
    string,
    {
      h2h?: Record<string, number>;
      correct_score?: Record<string, number>;
      exact_total?: Record<string, number>;
      exact_team_home?: Record<string, number>;
      exact_team_away?: Record<string, number>;
      handicap?: Record<string, Record<string, number>>;
      asian_handicap?: Record<string, Record<string, number>>;
    }
  >;
  firstHalfTotals?: Record<string, Record<string, number>>;
  secondHalfTotals?: Record<string, Record<string, number>>;
  inplaySummary: {
    probFinalHome: number;
    probFinalDraw: number;
    probFinalAway: number;
    probHtHome?: number;
    probHtDraw?: number;
    probHtAway?: number;
    probShHome?: number;
    probShDraw?: number;
    probShAway?: number;
    over25?: number;
    btts?: number;
    probNextGoalHome?: number;
    probNextGoalAway?: number;
    probNoMoreGoals?: number;
    topFinalScores?: Record<string, number>;
    htCorrectScores?: Record<string, number>;
    shCorrectScores?: Record<string, number>;
    htExactTotals?: Record<string, number>;
    shExactTotals?: Record<string, number>;
    htLineProbs?: Record<string, number>;
    secondHalfLineProbs?: Record<string, number>;
    htHandicapProbs?: Record<string, number>;
    shHandicapProbs?: Record<string, number>;
    ftHandicapProbs?: Record<string, number>;
    ftAsianHandicapProbs?: Record<string, number>;
    cornerLineProbs?: Record<string, number>;
    cardLineProbs?: Record<string, number>;
    refereeMarkets?: RefereeMarkets | null;
    refereeProfile?: RefereeProfile | null;
    halftimeAdjustment?: {
      applied?: boolean;
      home2hFactor?: number;
      away2hFactor?: number;
      reasons?: string[];
    };
    lambdaAdjustment?: {
      lambdaPriorHome: number;
      lambdaPriorAway: number;
      lambdaFullHome: number;
      lambdaFullAway: number;
      deltaHome: number;
      deltaAway: number;
      steps?: Array<Record<string, unknown>>;
    };
    modelBeforeDate?: string | null;
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
  againstModelAlerts: Array<{
    betId: string | null;
    market: string;
    betOutcome: OutcomeLabel;
    betOutcomeLabel: string;
    stake: number;
    oddsPlaced: number | null;
    pregamePalpite: OutcomeLabel;
    pregameProb: number;
    pregameUncertainty: string | null;
    inplayPalpite: OutcomeLabel;
    inplayProb: number;
    inplayProbs: Record<OutcomeLabel, number>;
    severity: "critical" | "high" | "medium";
    againstPregame: boolean;
    againstInplay: boolean;
    message: string;
  }>;
  betGuardrails: {
    enabled: boolean;
    blockNewBets: boolean;
    blockNewBets2h: boolean;
    allow2hSuggestions: boolean;
    blockMinute: number;
    block2hMinute: number;
    blockReason: string | null;
    oneBetPerMarket: boolean;
    pregamePalpite: OutcomeLabel | null;
    pregameProb: number | null;
    inplayPalpite: OutcomeLabel | null;
    inplayProb: number | null;
    htTrapWarnings: Array<{
      severity: string;
      code: string;
      title: string;
      reason: string;
      market?: string;
      outcome?: string;
      label?: string;
      minute?: number;
      currentGoals?: number;
      line?: number;
    }>;
    betBuilderRules: string[];
  } | null;
  liveStats: LiveMatchStats | null;
  scorealarm: ScorealarmContext | null;
  trendReport: LiveTrendReport | null;
  halfTickets: InplayHalfTickets | null;
  viable2hMarkets: Viable2hMarketsPanel | null;
  superMultipla: {
    minLegOddForBonus: number;
    bonusPct: number;
    defaultStake: number;
    suggestedCombos: Array<{
      id: string;
      stake: number;
      combinedOdd: number;
      productOdd?: number;
      pricingMode?: string;
      combinedProb: number;
      combinedEv: number | null;
      potentialPayout: number;
      bonusEligible: boolean;
      bonusPercentage: number;
      finalPayout: number;
      warnings: string[];
      legs: Array<{
        id?: string;
        market: string;
        outcome: string;
        label: string;
        marketOdd: number;
        modelProb: number;
        expectedValue?: number;
        edgePp?: number;
      }>;
    }>;
  } | null;
  optimizedTickets?: {
    tickets_1h: Array<{
      legs: Array<{
        market: string;
        outcome: string;
        label: string;
        modelProb: number;
        marketOdd: number;
        expectedValue: number;
        edgePp: number;
        kellyQuarter: number;
        classification: string;
      }>;
      combinedOdd: number;
      combinedProb: number;
      combinedEv: number;
      correlationPenalty: number;
      score: number;
      stakeBrl: number;
      stakePct: number;
      periodMix: string;
      nLegs: number;
      valid: boolean;
      validation: {
        valid: boolean;
        errors: Array<{ severity: string; code: string; reason: string }>;
        warnings: Array<{ severity: string; code: string; reason: string }>;
      };
    }>;
    tickets_2h: Array<{
      legs: Array<{
        market: string;
        outcome: string;
        label: string;
        modelProb: number;
        marketOdd: number;
        expectedValue: number;
        edgePp: number;
        kellyQuarter: number;
        classification: string;
      }>;
      combinedOdd: number;
      combinedProb: number;
      combinedEv: number;
      correlationPenalty: number;
      score: number;
      stakeBrl: number;
      stakePct: number;
      periodMix: string;
      nLegs: number;
      valid: boolean;
      validation: {
        valid: boolean;
        errors: Array<{ severity: string; code: string; reason: string }>;
        warnings: Array<{ severity: string; code: string; reason: string }>;
      };
    }>;
    tickets_ft: Array<{
      legs: Array<{
        market: string;
        outcome: string;
        label: string;
        modelProb: number;
        marketOdd: number;
        expectedValue: number;
        edgePp: number;
        kellyQuarter: number;
        classification: string;
      }>;
      combinedOdd: number;
      combinedProb: number;
      combinedEv: number;
      correlationPenalty: number;
      score: number;
      stakeBrl: number;
      stakePct: number;
      periodMix: string;
      nLegs: number;
      valid: boolean;
      validation: {
        valid: boolean;
        errors: Array<{ severity: string; code: string; reason: string }>;
        warnings: Array<{ severity: string; code: string; reason: string }>;
      };
    }>;
    tickets_mixed: Array<{
      legs: Array<{
        market: string;
        outcome: string;
        label: string;
        modelProb: number;
        marketOdd: number;
        expectedValue: number;
        edgePp: number;
        kellyQuarter: number;
        classification: string;
      }>;
      combinedOdd: number;
      combinedProb: number;
      combinedEv: number;
      correlationPenalty: number;
      score: number;
      stakeBrl: number;
      stakePct: number;
      periodMix: string;
      nLegs: number;
      valid: boolean;
      validation: {
        valid: boolean;
        errors: Array<{ severity: string; code: string; reason: string }>;
        warnings: Array<{ severity: string; code: string; reason: string }>;
      };
    }>;
  } | null;
  matchContext: {
    referee_name?: string;
    referee_card_lambda?: number;
    referee_penalty_rate?: number;
    home_pregame_xg?: number;
    away_pregame_xg?: number;
    h2h_avg_goals?: number;
    source_filename?: string;
    notes?: string[];
  } | null;
}

export interface Viable2hMarketRow {
  market: string;
  outcome: string;
  label: string;
  shortLabel: string;
  category: string;
  categoryLabel: string;
  modelProb: number;
  marketOdd: number;
  impliedProb: number;
  expectedValue: number;
  edgePp: number;
  meetsThreshold: boolean;
  viabilityScore: number;
}

export interface Viable2hMarketsPanel {
  available: boolean;
  closed: boolean;
  closedReason: string | null;
  minute: number;
  minutesRemaining: number;
  remainingFraction: number;
  block2hMinute: number;
  minModelProb: number;
  markets: Viable2hMarketRow[];
  chart: {
    categories: string[];
    probabilitiesPct: number[];
    evPct: number[];
  };
}

export interface InplayTicketLeg {
  market: string;
  outcome: string;
  label: string;
  modelProb: number;
  marketOdd: number;
  expectedValue: number;
  edgePp: number;
  suggestedStakePct?: number;
  suggestedStakeValue?: number;
}

export interface InplayTicketCombo {
  id: string;
  title: string;
  legs: InplayTicketLeg[];
  combinedOdd: number;
  combinedProb: number;
  combinedEv: number;
  suggestedStakePct: number;
  suggestedStakeValue: number;
  notes: string[];
}

export interface InplayHalfPeriodTickets {
  available: boolean;
  closed: boolean;
  closedReason: string | null;
  singles: InplayTicketLeg[];
  combos: InplayTicketCombo[];
}

export interface InplayHalfTickets {
  firstHalf: InplayHalfPeriodTickets;
  secondHalf: InplayHalfPeriodTickets;
  mixedCombos: InplayTicketCombo[];
}

export interface LiveMatchStats {
  source: string | null;
  possessionSource: string | null;
  sofascoreEventId: number | null;
  sofascoreAvailable: boolean;
  scorealarmAvailable: boolean;
  scorealarmStale: boolean;
  homeXg: number | null;
  awayXg: number | null;
  homePossessionPct: number | null;
  awayPossessionPct: number | null;
  homeShotsOnTarget: number | null;
  awayShotsOnTarget: number | null;
  homeCorners: number | null;
  awayCorners: number | null;
  homeYellowCards: number | null;
  awayYellowCards: number | null;
  homeRedCards: number | null;
  awayRedCards: number | null;
  warnings: string[];
}

export interface ScorealarmTimelineEvent {
  minute: number;
  addedTime: number | null;
  team: string;
  side: number;
  type: number;
  subtype: number;
  label: string;
  icon: string;
  score: string | null;
}

export interface ScorealarmH2h {
  homeWins: number;
  draws: number;
  awayWins: number;
  sinceYear: number | null;
}

export interface ScorealarmLastMatch {
  opponent: string;
  score: string;
  result: string;
  goalsFor: number;
  goalsAgainst: number;
}

export interface ScorealarmTeamForm {
  team: string;
  form: string;
  wins: number;
  draws: number;
  losses: number;
  goalsAvg: number;
  concededAvg: number;
  coach: string | null;
  lastMatches: ScorealarmLastMatch[];
}

export interface ScorealarmH2hMatch {
  homeTeam: string;
  awayTeam: string;
  score: string;
}

export interface ScorealarmPrematch {
  home: ScorealarmTeamForm;
  away: ScorealarmTeamForm;
  h2hMatches: ScorealarmH2hMatch[];
}

export interface ScorealarmTopPlayer {
  name: string;
  team: string;
  side: number;
  jersey: string;
  positionLabel: string;
  stats: Record<string, number>;
  highlights: string[];
}

export interface ScorealarmSocialPick {
  label: string;
  market: string;
  outcome: string;
  odd: number | null;
  betCount: number | null;
  sharePct: number | null;
}

export interface ScorealarmSocial {
  available: boolean;
  source: string;
  reason: string | null;
  picks: ScorealarmSocialPick[];
}

export interface ScorealarmContext {
  available: boolean;
  stale: boolean;
  timeline: ScorealarmTimelineEvent[];
  h2h: ScorealarmH2h | null;
  prematch: ScorealarmPrematch | null;
  players: ScorealarmTopPlayer[];
  social: ScorealarmSocial | null;
  stats: Record<string, number>;
  scoresId: string | null;
}

export interface RefereeProfile {
  name: string;
  country: string | null;
  cardLambda: number;
  foulLambda: number;
  penaltyLambda: number;
  redCardLambda: number;
  classification: "punitivista" | "equilibrado" | "pacificador";
  classificationPt: string;
  cardFoulRatio: number;
  avgCardsPerGame: number;
  avgFoulsPerGame: number;
}

export interface RefereeMarketLine {
  line: number;
  overProb: number;
  underProb: number;
  overOddsFair: number;
  underOddsFair: number;
  expectedTotal: number;
  recommendation: "over" | "under" | "neutro";
  confidence: "alta" | "media" | "baixa";
  edge: number | null;
}

export interface RefereeMarkets {
  yellowCards: {
    current: number;
    expectedRemaining: number;
    expectedTotal: number;
    overLines: RefereeMarketLine[];
    metadata: {
      refereeName: string;
      classification: string;
      classificationPt: string;
      cardLambda: number;
      minute: number;
      remainingMinutes: number;
    };
  };
  redCards: {
    yesProb: number;
    yesOddsFair: number;
    recommendation: "sim" | "nao" | "neutro";
    confidence: string;
  };
  penalties: {
    yesProb: number;
    yesOddsFair: number;
    recommendation: "sim" | "nao" | "neutro";
    confidence: string;
  };
  fouls: {
    expectedTotal: number;
    overLines: RefereeMarketLine[];
  };
}

export interface LiveTrendReport {
  eventId: number;
  homeTeam: string;
  awayTeam: string;
  currentScore: string | null;
  minute: number;
  dominantTrend: string | null;
  signals: Array<{
    type: string;
    direction: string;
    strength: number;
    description: string;
    minute: number | null;
  }>;
  positionAdvice: {
    action: string;
    urgency: string;
    reasoning: string;
    repositionTo: string | null;
    repositionDetail: string | null;
    repositionOdd: number | null;
    confidence: number;
  } | null;
  bestOpportunities: Array<Record<string, unknown>>;
}

/** Bilhete combo KXL (pré-jogo ou in-play via strategy.comboTicket). */
export type WcComboTicket = NonNullable<NonNullable<SuperbetLiveAdvice["strategy"]>["comboTicket"]>;

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
  realPoints: number;
  realPlayed: number;
  realGd: number;
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
  asOf: string;
  nRealResults: number;
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
  bonusEligible?: boolean | null;
  bonusPercentage?: number | null;
  finalPayout?: number | null;
}

export interface UserOpenBetsList {
  count: number;
  bets: UserOpenBet[];
}

// ---------------------------------------------------------------------------
// Basquete In-Play (NBA / Superbet)
// ---------------------------------------------------------------------------

export interface BasketSuperbetLiveEvent {
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

export interface BasketSuperbetLiveFeed {
  count: number;
  sportId: number | null;
  events: BasketSuperbetLiveEvent[];
  capturedAt: string;
}

export interface BasketInPlaySummary {
  probHomeWin: number | null;
  probAwayWin: number | null;
  expectedFinalHome: number | null;
  expectedFinalAway: number | null;
  expectedTotal: number | null;
  remainingMinutes: number | null;
  moneylineProbs: Record<string, number>;
  spreadProbs: Record<string, number>;
  totalProbs: Record<string, number>;
  ppmHome: number | null;
  ppmAway: number | null;
  ppmHomePrior: number | null;
  ppmAwayPrior: number | null;
  matchMinutes: number | null;
  nSimulations: number | null;
  marketTotalLine: number | null;
  marketSpreadLine: number | null;
  nextQuarterNumber: number | null;
  nextQuarterProjectionHome: number | null;
  nextQuarterProjectionAway: number | null;
}

export interface BasketQuarterScore {
  num: number;
  home: number;
  away: number;
}

export interface BasketAporteAdvice {
  market: string;
  outcome: string;
  label: string;
  modelProb: number;
  marketOdd: number;
  impliedProb: number;
  expectedValue: number;
  edgePp: number;
  kellyQuarter: number;
  suggestedStakePct: number;
  suggestedStakeValue: number | null;
  action: string;
}

export interface BasketConfidence {
  score: number;
  label: string;
  maxEdgePp: number;
}

export interface BasketSuperbetLiveAdvice {
  homeTeam: string;
  awayTeam: string;
  minute: number;
  currentScore: string | null;
  periodLabel: string | null;
  status: string | null;
  basketPeriods: BasketQuarterScore[];
  isFinished: boolean;
  isLive: boolean;
  superbetStale: boolean;
  superbetEventId: number;
  sportId: number | null;
  capturedAt: string | null;
  h2hOdds: Record<string, number>;
  h2hImplied: Record<string, number>;
  spreadOdds: Record<string, Record<string, number>>;
  spreadImplied: Record<string, Record<string, number>>;
  totalPointsOdds: Record<string, Record<string, number>>;
  totalPointsImplied: Record<string, Record<string, number>>;
  inplaySummary: BasketInPlaySummary;
  aportes: BasketAporteAdvice[];
  confidence: BasketConfidence | null;
}

/** Feed ao vivo de beisebol — mesmo shape da lista de basquete. */
export type BaseballSuperbetLiveEvent = BasketSuperbetLiveEvent;
export type BaseballSuperbetLiveFeed = BasketSuperbetLiveFeed;

export interface BaseballInPlaySummary {
  probHomeWin: number | null;
  probAwayWin: number | null;
  expectedFinalHome: number | null;
  expectedFinalAway: number | null;
  expectedTotal: number | null;
  remainingInnings: number | null;
  moneylineProbs: Record<string, number>;
  spreadProbs: Record<string, number>;
  totalProbs: Record<string, number>;
  rpiHome: number | null;
  rpiAway: number | null;
  rpiHomePrior: number | null;
  rpiAwayPrior: number | null;
  matchInnings: number | null;
  nSimulations: number | null;
  marketTotalLine: number | null;
  marketSpreadLine: number | null;
}

export interface BaseballInningScore {
  num: number;
  home: number;
  away: number;
}

export interface BaseballSuperbetLiveAdvice {
  homeTeam: string;
  awayTeam: string;
  inning: number;
  minute: number;
  currentScore: string | null;
  periodLabel: string | null;
  status: string | null;
  baseballInnings: BaseballInningScore[];
  isFinished: boolean;
  isLive: boolean;
  superbetStale: boolean;
  superbetEventId: number;
  sportId: number | null;
  capturedAt: string | null;
  h2hOdds: Record<string, number>;
  h2hImplied: Record<string, number>;
  spreadOdds: Record<string, Record<string, number>>;
  spreadImplied: Record<string, Record<string, number>>;
  totalRunsOdds: Record<string, Record<string, number>>;
  totalRunsImplied: Record<string, Record<string, number>>;
  inplaySummary: BaseballInPlaySummary;
  aportes: BasketAporteAdvice[];
  confidence: BasketConfidence | null;
}

export interface LiveCopilotPick {
  rank: number;
  market: string;
  outcome: string;
  label: string;
  rationale: string;
  confidence: string;
  modelProb?: number | null;
  marketOdd?: number | null;
  expectedValue?: number | null;
  edgePp?: number | null;
  suggestedStakePct?: number | null;
}

export interface LiveCopilot {
  enabled: boolean;
  available: boolean;
  sport: string;
  eventId: number;
  capturedAt: string | null;
  cached: boolean;
  model: string | null;
  error: string | null;
  waitReason: string | null;
  momento: string;
  acaoAgora: "apostar" | "aguardar" | "cashout";
  confiancaGeral: string;
  picks: LiveCopilotPick[];
  alertas: string[];
  bilhete: LiveCopilotBilhete | null;
}

export type LiveCopilotUiActionType = "notify" | "add_ticket_legs" | "switch_tab";

export type LiveCopilotTabId = "resumo" | "mercados" | "qualidade" | "bilhete";

export interface LiveCopilotUiLeg {
  market: string;
  outcome: string;
  label: string;
  modelProb?: number | null;
  marketOdd?: number | null;
  expectedValue?: number | null;
  edgePp?: number | null;
  suggestedStakePct?: number | null;
}

export interface LiveCopilotUiAction {
  type: LiveCopilotUiActionType;
  title?: string | null;
  body?: string | null;
  tab?: LiveCopilotTabId | null;
  legs: LiveCopilotUiLeg[];
}

export interface LiveCopilotChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface LiveCopilotAgent extends LiveCopilot {
  mode: string;
  reply: string;
  toolsUsed: string[];
  uiActions: LiveCopilotUiAction[];
  autoApplyUi: boolean;
}

export interface LiveCopilotBilheteLeg {
  rank: number;
  market: string;
  outcome: string;
  label: string;
  papel: string;
  rationale: string;
  marketOdd?: number | null;
  modelProb?: number | null;
  expectedValue?: number | null;
  edgePp?: number | null;
}

export interface LiveCopilotBilhete {
  tipo: string;
  titulo: string;
  resumo: string;
  pernas: LiveCopilotBilheteLeg[];
  valid: boolean;
  combinedOdd?: number | null;
  combinedOddSimple?: number | null;
  pricingMode?: string | null;
  avisosCorrelacao: string[];
  validationWarnings: string[];
}
