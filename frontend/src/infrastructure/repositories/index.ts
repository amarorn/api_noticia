import type {
  IBrasileiraoRepository,
  IHealthRepository,
  IWcRepository,
} from "@/domain/repositories";
import { apiFetch } from "../api/client";
import {
  mapBrasileiraoRound,
  mapHealth,
  mapValueBets,
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
    const raw = await apiFetch<Parameters<typeof mapWcRound>[0]>(`/worldcup/round${qs}`);
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

  async predictMatch(homeTeam: string, awayTeam: string, phase: string) {
    const raw = await apiFetch<Parameters<typeof mapWcPrediction>[0]>("/worldcup/predict", {
      method: "POST",
      body: JSON.stringify({
        home_team: homeTeam,
        away_team: awayTeam,
        phase,
      }),
    });
    return mapWcPrediction(raw);
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
