import type {
  IBrasileiraoRepository,
  IHealthRepository,
  IWcRepository,
} from "@/domain/repositories";
import { apiFetch, API_SYNC_TIMEOUT_MS } from "../api/client";
import {
  mapBrasileiraoRound,
  mapHealth,
  mapSofascoreResolvedEvent,
  mapValueBets,
  mapWcCornersPrediction,
  mapWcPrediction,
  mapWcRound,
  mapWcSchedule,
  mapWcSquadDetail,
  mapWcSquadsIndex,
  mapWcGroupStandings,
} from "../mappers";

export class WcApiRepository implements IWcRepository {
  async getRound(matchday?: number) {
    const qs = matchday != null ? `?round=${matchday}` : "";
    const raw = await apiFetch<Parameters<typeof mapWcRound>[0]>(`/worldcup/round${qs}`, {
      timeoutMs: API_SYNC_TIMEOUT_MS,
    });
    return mapWcRound(raw);
  }

  async getSchedule() {
    const raw = await apiFetch<Parameters<typeof mapWcSchedule>[0]>("/worldcup/schedule");
    return mapWcSchedule(raw);
  }

  async getSquadsIndex() {
    const raw = await apiFetch<Parameters<typeof mapWcSquadsIndex>[0]>("/worldcup/squads");
    return mapWcSquadsIndex(raw);
  }

  async getSquad(team: string) {
    const raw = await apiFetch<Parameters<typeof mapWcSquadDetail>[0]>(
      `/worldcup/squads/${encodeURIComponent(team)}`,
    );
    return mapWcSquadDetail(raw);
  }

  async predictMatch(dto: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
    sofascoreEventId?: number;
  }) {
    const usesSofascore = dto.sofascoreEventId != null;
    const raw = await apiFetch<Parameters<typeof mapWcPrediction>[0]>("/worldcup/predict", {
      method: "POST",
      timeoutMs: usesSofascore ? API_SYNC_TIMEOUT_MS : undefined,
      body: JSON.stringify({
        home_team: dto.homeTeam,
        away_team: dto.awayTeam,
        phase: dto.phase,
        ...(usesSofascore ? { sofascore_event_id: dto.sofascoreEventId } : {}),
      }),
    });
    return mapWcPrediction(raw);
  }

  async predictCorners(dto: { homeTeam: string; awayTeam: string; phase: string }) {
    const raw = await apiFetch<Parameters<typeof mapWcCornersPrediction>[0]>(
      "/worldcup/corners/predict",
      {
        method: "POST",
        body: JSON.stringify({
          home_team: dto.homeTeam,
          away_team: dto.awayTeam,
          phase: dto.phase,
        }),
      },
    );
    return mapWcCornersPrediction(raw);
  }

  async resolveSofascoreEvent(dto: {
    homeTeam: string;
    awayTeam: string;
    date: string;
  }) {
    const params = new URLSearchParams({
      home_team: dto.homeTeam,
      away_team: dto.awayTeam,
      date: dto.date,
    });
    const raw = await apiFetch<Parameters<typeof mapSofascoreResolvedEvent>[0]>(
      `/worldcup/sofascore/resolve?${params}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapSofascoreResolvedEvent(raw);
  }

  async getTeams() {
    const raw = await apiFetch<{ teams: string[] }>("/worldcup/teams");
    return raw.teams;
  }

  async getValueBets() {
    const raw = await apiFetch<Parameters<typeof mapValueBets>[0]>("/worldcup/value/live", {
      method: "POST",
      body: JSON.stringify({ save_odds_file: false }),
    });
    return mapValueBets(raw);
  }

  async getGroupStandings() {
    const raw = await apiFetch<Parameters<typeof mapWcGroupStandings>[0]>(
      "/worldcup/group-standings",
    );
    return mapWcGroupStandings(raw);
  }
}

export class BrasileiraoApiRepository implements IBrasileiraoRepository {
  async getRoundPredictions() {
    const raw = await apiFetch<Parameters<typeof mapBrasileiraoRound>[0]>("/round/predict");
    return mapBrasileiraoRound(raw);
  }
}

export class HealthApiRepository implements IHealthRepository {
  async getHealth() {
    const raw = await apiFetch<Parameters<typeof mapHealth>[0]>("/health");
    return mapHealth(raw);
  }
}

export { historicalValidationRepository } from "./historicalValidationRepository";
export { newsRepository } from "./newsRepository";
export const wcRepository = new WcApiRepository();
export const brasileiraoRepository = new BrasileiraoApiRepository();
export const healthRepository = new HealthApiRepository();
