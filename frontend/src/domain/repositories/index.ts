import type {
  BrasileiraoRound,
  HealthStatus,
  NewsFeed,
  NewsSyncResult,
  ValueBetsReport,
  WcPrediction,
  WcRound,
  WcSchedule,
} from "../entities";

export interface NewsFeedParams {
  limit?: number;
  offset?: number;
  source?: string | null;
  query?: string | null;
  days?: number;
}

export interface IWcRepository {
  getRound(): Promise<WcRound>;
  getSchedule(): Promise<WcSchedule>;
  predictMatch(homeTeam: string, awayTeam: string, phase: string): Promise<WcPrediction>;
  getTeams(): Promise<string[]>;
  getValueBets(): Promise<ValueBetsReport>;
}

export interface IBrasileiraoRepository {
  getRoundPredictions(): Promise<BrasileiraoRound>;
}

export interface IHealthRepository {
  getHealth(): Promise<HealthStatus>;
}

export interface INewsRepository {
  syncSources(): Promise<NewsSyncResult>;
  getFeed(params: NewsFeedParams): Promise<NewsFeed>;
}

export type {
  IHistoricalValidationRepository,
  ValidateHistoricalMatchRequest,
} from "./historicalValidationRepository";
