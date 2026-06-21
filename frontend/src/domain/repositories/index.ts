import type {
  BrasileiraoRound,
  HealthStatus,
  NewsCards,
  NewsFeed,
  NewsSyncResult,
  SofascoreResolvedEvent,
  ValueBetsReport,
  HandicapAnalysis,
  WcCornersPrediction,
  WcInPlayPrediction,
  WcPrediction,
  WcRound,
  WcSchedule,
  WcSquadDetail,
  WcSquadsIndex,
  WcGroupStandings,
  WcFriendlies,
} from "../entities";

export interface NewsFeedParams {
  limit?: number;
  offset?: number;
  source?: string | null;
  query?: string | null;
  days?: number;
}

export interface NewsAllParams {
  offset?: number;
  source?: string | null;
  query?: string | null;
  days?: number | null;
  team?: string | null;
  homeTeam?: string | null;
  awayTeam?: string | null;
  teams?: string[] | null;
}

export interface NewsCardsParams {
  limit?: number;
  offset?: number;
  source?: string | null;
  query?: string | null;
  days?: number;
  team?: string | null;
  homeTeam?: string | null;
  awayTeam?: string | null;
  teams?: string[] | null;
}

export interface IWcRepository {
  getRound(matchday?: number): Promise<WcRound>;
  getSchedule(): Promise<WcSchedule>;
  getSquadsIndex(): Promise<WcSquadsIndex>;
  getSquad(team: string): Promise<WcSquadDetail>;
  predictMatch(request: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
    sofascoreEventId?: number;
  }): Promise<WcPrediction>;
  predictCorners(request: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
  }): Promise<WcCornersPrediction>;
  predictInPlay(request: {
    homeTeam: string;
    awayTeam: string;
    homeScore: number;
    awayScore: number;
    minute: number;
    phase?: string;
    matchMinutes?: number;
    superbetEventId?: number;
  }): Promise<WcInPlayPrediction>;
  getHandicapAnalysis(request: {
    eventId: number;
    bankroll?: number;
    phase?: string;
  }): Promise<HandicapAnalysis>;
  resolveSofascoreEvent(request: {
    homeTeam: string;
    awayTeam: string;
    date: string;
  }): Promise<SofascoreResolvedEvent>;
  getTeams(): Promise<string[]>;
  getValueBets(): Promise<ValueBetsReport>;
  getGroupStandings(): Promise<WcGroupStandings>;
  getFriendlies(request: {
    team: string;
    includeFinished?: boolean;
    includeUpcoming?: boolean;
  }): Promise<WcFriendlies>;
  getSuperbetLive(request?: {
    sportId?: number;
    allSports?: boolean;
    rank?: boolean;
  }): Promise<import("@/domain/entities").SuperbetLiveFeed>;
  getSuperbetEvent(request: {
    eventId: number;
    saveBronze?: boolean;
  }): Promise<import("@/domain/entities").SuperbetEventSnapshot>;
  getSuperbetLiveAdvice(request: {
    eventId: number;
    phase?: string;
    bankroll?: number;
    market?: string;
    outcome?: string;
    stake?: number;
    oddsPlaced?: number;
    fast?: boolean;
    kickoff?: string;
  }): Promise<import("@/domain/entities").SuperbetLiveAdvice>;
  getComboTicket(request: {
    homeTeam: string;
    awayTeam: string;
    bankroll?: number;
    superbetEventId?: number;
  }): Promise<import("@/domain/entities").WcComboTicket>;
  calculateSuperMultipla(request: {
    legs: import("@/presentation/utils/superMultipla").SuperMultiplaCalculateLeg[];
    stake: number;
    betType?: "SIMPLE" | "MULTIPLE";
    minute?: number;
    homeScore?: number;
    awayScore?: number;
    superbetEventId?: number;
  }): Promise<import("@/presentation/utils/superMultipla").SuperMultiplaCalculateResult>;
  simulateMatch(request: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
    matchDate?: string;
    fifaMatchId?: string;
    sofascoreEventId?: number;
  }): Promise<import("@/domain/entities").WcSimulation>;
  getUserOpenBets(): Promise<import("@/domain/entities").UserOpenBetsList>;
  refreshOpenBetsCashouts(eventId?: number): Promise<{
    updated: number;
    skipped: number;
    errors: number;
  }>;
  registerComboProposal(
    body: import("@/application/dtos/comboProposal").ComboProposalApiBody,
  ): Promise<import("@/application/dtos/comboProposal").RegisterComboProposalResult>;
}

export interface IBrasileiraoRepository {
  getRoundPredictions(): Promise<BrasileiraoRound>;
}

export interface IHealthRepository {
  getHealth(): Promise<HealthStatus>;
}

export interface NewsSyncOptions {
  /** Baixa HTML completo de cada URL (padrão: true na UI). */
  fetchBody?: boolean;
  /** Reprocessa todo o bronze no silver (use no botão “Atualizar”). */
  fullRebuild?: boolean;
}

export interface INewsRepository {
  syncSources(options?: NewsSyncOptions): Promise<NewsSyncResult>;
  getFeed(params: NewsFeedParams): Promise<NewsFeed>;
  getCards(params: NewsCardsParams): Promise<NewsCards>;
  getAll(params: NewsAllParams): Promise<NewsFeed>;
}

export type {
  IHistoricalValidationRepository,
  ValidateHistoricalMatchRequest,
} from "./historicalValidationRepository";
