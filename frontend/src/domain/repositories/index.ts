import type {
  BrasileiraoRound,
  HealthStatus,
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

export interface INewsRepository {
  syncSources(): Promise<NewsSyncResult>;
  getFeed(params: NewsFeedParams): Promise<NewsFeed>;
}

export type {
  IHistoricalValidationRepository,
  ValidateHistoricalMatchRequest,
} from "./historicalValidationRepository";
