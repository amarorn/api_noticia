import type {
  HistoricalValidationResult,
  WcEdition,
  WcHistoricalMatch,
} from "../entities";

export interface ValidateHistoricalMatchRequest {
  season: number;
  matchId?: string;
  homeTeam?: string;
  awayTeam?: string;
}

export interface IHistoricalValidationRepository {
  getEditions(): Promise<WcEdition[]>;
  getEditionMatches(season: number): Promise<WcHistoricalMatch[]>;
  validateMatch(request: ValidateHistoricalMatchRequest): Promise<HistoricalValidationResult>;
}
