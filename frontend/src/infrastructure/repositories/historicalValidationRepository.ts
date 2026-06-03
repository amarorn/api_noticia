import type {
  IHistoricalValidationRepository,
  ValidateHistoricalMatchRequest,
} from "@/domain/repositories";
import { apiFetch } from "../api/client";
import {
  mapHistoricalValidation,
  mapWcEdition,
  mapWcHistoricalMatch,
} from "../mappers/historicalValidationMappers";

export class HistoricalValidationApiRepository
  implements IHistoricalValidationRepository
{
  async getEditions() {
    const raw = await apiFetch<{ editions: Parameters<typeof mapWcEdition>[0][] }>(
      "/worldcup/editions",
    );
    return raw.editions.map(mapWcEdition);
  }

  async getEditionMatches(season: number) {
    const raw = await apiFetch<{
      season: number;
      matches: Parameters<typeof mapWcHistoricalMatch>[0][];
    }>(`/worldcup/editions/${season}/matches`);
    return raw.matches.map(mapWcHistoricalMatch);
  }

  async validateMatch(request: ValidateHistoricalMatchRequest) {
    const body: Record<string, unknown> = { season: request.season };
    if (request.matchId) {
      body.match_id = request.matchId;
    } else {
      body.home_team = request.homeTeam;
      body.away_team = request.awayTeam;
    }
    const raw = await apiFetch<Parameters<typeof mapHistoricalValidation>[0]>(
      "/worldcup/validate",
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
    return mapHistoricalValidation(raw);
  }
}

export const historicalValidationRepository = new HistoricalValidationApiRepository();
