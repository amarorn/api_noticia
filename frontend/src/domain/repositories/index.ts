import type {
  BrasileiraoRound,
  HealthStatus,
  NewsCards,
  NewsCards,
  NewsFeed,
  NewsSyncResult,
  ValueBetsReport,
  WcPrediction,
  WcRound,
  WcSchedule,
  WcSquadDetail,
  WcSquadsIndex,
  WcGroupStandings,
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
  predictMatch(homeTeam: string, awayTeam: string, phase: string): Promise<WcPrediction>;
  getTeams(): Promise<string[]>;
  getValueBets(): Promise<ValueBetsReport>;
  getGroupStandings(): Promise<WcGroupStandings>;
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
