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
  mapWcInPlayPrediction,
  mapWcPrediction,
  mapWcRound,
  mapWcSchedule,
  mapWcSquadDetail,
  mapWcSquadsIndex,
  mapWcGroupStandings,
  mapWcFriendlies,
  mapSuperbetLiveFeed,
  mapSuperbetLiveAdvice,
  mapSuperbetEvent,
  mapComboTicket,
  mapHandicapAnalysis,
  mapWcSimulation,
  mapUserOpenBets,
  mapBasketSuperbetLiveFeed,
  mapBasketSuperbetLiveAdvice,
  mapBasketMultiGameTickets,
  mapBaseballSuperbetLiveFeed,
  mapBaseballSuperbetLiveAdvice,
  mapBaseballSuperbetEvent,
  mapLiveCopilot,
  mapLiveCopilotAgent,
} from "../mappers";
import {
  mapSuperMultiplaCalculate,
  type SuperMultiplaCalculateLeg,
} from "@/presentation/utils/superMultipla";

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

  async predictInPlay(dto: {
    homeTeam: string;
    awayTeam: string;
    homeScore: number;
    awayScore: number;
    minute: number;
    phase?: string;
    matchMinutes?: number;
    superbetEventId?: number;
  }) {
    const raw = await apiFetch<Parameters<typeof mapWcInPlayPrediction>[0]>(
      "/worldcup/inplay",
      {
        method: "POST",
        body: JSON.stringify({
          home_team: dto.homeTeam,
          away_team: dto.awayTeam,
          home_score: dto.homeScore,
          away_score: dto.awayScore,
          minute: dto.minute,
          phase: dto.phase ?? "group",
          ...(dto.matchMinutes != null ? { match_minutes: dto.matchMinutes } : {}),
          ...(dto.superbetEventId != null
            ? { superbet_event_id: dto.superbetEventId, merge_superbet_odds: true }
            : {}),
        }),
      },
    );
    return mapWcInPlayPrediction(raw);
  }

  async getHandicapAnalysis(dto: { eventId: number; bankroll?: number; phase?: string }) {
    const params = new URLSearchParams();
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.phase) params.set("phase", dto.phase);
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapHandicapAnalysis>[0]>(
      `/worldcup/handicap/${dto.eventId}${qs}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapHandicapAnalysis(raw);
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

  async getFriendlies(dto: {
    team: string;
    includeFinished?: boolean;
    includeUpcoming?: boolean;
  }) {
    const params = new URLSearchParams({ team: dto.team });
    if (dto.includeFinished === false) {
      params.set("include_finished", "false");
    }
    if (dto.includeUpcoming === false) {
      params.set("include_upcoming", "false");
    }
    const raw = await apiFetch<Parameters<typeof mapWcFriendlies>[0]>(
      `/worldcup/friendlies?${params}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapWcFriendlies(raw);
  }

  async getSuperbetLive(dto?: { sportId?: number; allSports?: boolean; rank?: boolean }) {
    const params = new URLSearchParams();
    if (dto?.sportId != null) {
      params.set("sport_id", String(dto.sportId));
    }
    if (dto?.allSports) {
      params.set("all_sports", "true");
    }
    if (dto?.rank === false) {
      params.set("rank", "false");
    }
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapSuperbetLiveFeed>[0]>(
      `/worldcup/superbet/live${qs}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapSuperbetLiveFeed(raw);
  }

  async getSuperbetEvent(dto: { eventId: number; saveBronze?: boolean }) {
    const params = new URLSearchParams();
    if (dto.saveBronze === false) params.set("save_bronze", "false");
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapSuperbetEvent>[0]>(
      `/worldcup/superbet/events/${dto.eventId}${qs}`,
      { timeoutMs: 30_000 },
    );
    return mapSuperbetEvent(raw);
  }

  async getComboTicket(dto: {
    homeTeam: string;
    awayTeam: string;
    bankroll?: number;
    superbetEventId?: number;
  }) {
    const params = new URLSearchParams({
      home_team: dto.homeTeam,
      away_team: dto.awayTeam,
    });
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.superbetEventId != null) {
      params.set("superbet_event_id", String(dto.superbetEventId));
    }
    const raw = await apiFetch<Record<string, unknown>>(
      `/worldcup/combo-ticket?${params}`,
      { timeoutMs: 30_000 },
    );
    return mapComboTicket(raw)!;
  }

  async calculateSuperMultipla(dto: {
    legs: SuperMultiplaCalculateLeg[];
    stake: number;
    betType?: "SIMPLE" | "MULTIPLE";
    minute?: number;
    homeScore?: number;
    awayScore?: number;
    superbetEventId?: number;
  }) {
    const raw = await apiFetch<Record<string, unknown>>(
      "/worldcup/superbet/multiple/calculate",
      {
        method: "POST",
        body: JSON.stringify({
          legs: dto.legs,
          stake: dto.stake,
          bet_type: dto.betType ?? "MULTIPLE",
          minute: dto.minute,
          home_score: dto.homeScore ?? 0,
          away_score: dto.awayScore ?? 0,
          superbet_event_id: dto.superbetEventId,
        }),
        timeoutMs: 15_000,
      },
    );
    return mapSuperMultiplaCalculate(raw);
  }

  async getSuperbetLiveAdvice(dto: {
    eventId: number;
    phase?: string;
    bankroll?: number;
    market?: string;
    outcome?: string;
    stake?: number;
    oddsPlaced?: number;
    fast?: boolean;
    kickoff?: string;
  }) {
    const params = new URLSearchParams();
    if (dto.phase) params.set("phase", dto.phase);
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.market) params.set("market", dto.market);
    if (dto.outcome) params.set("outcome", dto.outcome);
    if (dto.stake != null) params.set("stake", String(dto.stake));
    if (dto.oddsPlaced != null) params.set("odds_placed", String(dto.oddsPlaced));
    if (dto.fast) params.set("fast", "true");
    if (dto.kickoff) params.set("kickoff", dto.kickoff);
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapSuperbetLiveAdvice>[0]>(
      `/worldcup/superbet/live/${dto.eventId}/advice${qs}`,
      { timeoutMs: dto.fast ? 60_000 : API_SYNC_TIMEOUT_MS },
    );
    return mapSuperbetLiveAdvice(raw);
  }

  async simulateMatch(dto: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
    matchDate?: string;
    fifaMatchId?: string;
    sofascoreEventId?: number;
  }) {
    const raw = await apiFetch<Parameters<typeof mapWcSimulation>[0]>("/worldcup/simulate", {
      method: "POST",
      timeoutMs: API_SYNC_TIMEOUT_MS,
      body: JSON.stringify({
        home_team: dto.homeTeam,
        away_team: dto.awayTeam,
        phase: dto.phase,
        ...(dto.matchDate ? { match_date: dto.matchDate } : {}),
        ...(dto.fifaMatchId ? { fifa_match_id: dto.fifaMatchId } : {}),
        ...(dto.sofascoreEventId != null ? { sofascore_event_id: dto.sofascoreEventId } : {}),
      }),
    });
    return mapWcSimulation(raw);
  }

  async getUserOpenBets() {
    const raw = await apiFetch<Parameters<typeof mapUserOpenBets>[0]>("/user/open-bets?include_proposals=false", {
      timeoutMs: API_SYNC_TIMEOUT_MS,
    });
    return mapUserOpenBets(raw);
  }

  async refreshOpenBetsCashouts(eventId?: number) {
    const qs = eventId != null ? `?event_id=${eventId}` : "";
    return apiFetch<{ updated: number; skipped: number; errors: number }>(
      `/user/open-bets/refresh-cashouts${qs}`,
      { method: "POST", timeoutMs: API_SYNC_TIMEOUT_MS },
    );
  }

  async registerComboProposal(body: import("@/application/dtos/comboProposal").ComboProposalApiBody) {
    return apiFetch<import("@/application/dtos/comboProposal").RegisterComboProposalResult>(
      "/user/open-bets",
      {
        method: "POST",
        timeoutMs: API_SYNC_TIMEOUT_MS,
        body: JSON.stringify(body),
      },
    );
  }

  async getBasketSuperbetLive(dto?: { sportId?: number; allSports?: boolean }) {
    const params = new URLSearchParams();
    if (dto?.sportId != null) {
      params.set("sport_id", String(dto.sportId));
    }
    if (dto?.allSports) {
      params.set("all_sports", "true");
    }
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapBasketSuperbetLiveFeed>[0]>(
      `/basket/superbet/live${qs}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapBasketSuperbetLiveFeed(raw);
  }

  async getBasketSuperbetLiveAdvice(dto: { eventId: number; bankroll?: number; fast?: boolean }) {
    const params = new URLSearchParams();
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.fast) params.set("fast", "true");
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapBasketSuperbetLiveAdvice>[0]>(
      `/basket/superbet/live/${dto.eventId}/advice${qs}`,
      { timeoutMs: dto.fast ? 60_000 : API_SYNC_TIMEOUT_MS },
    );
    return mapBasketSuperbetLiveAdvice(raw);
  }

  async buildBasketMultiGameTickets(dto: {
    eventIds: number[];
    bankroll?: number;
    stake?: number;
    minLegs?: number;
    maxLegs?: number;
    maxTickets?: number;
    requireApostar?: boolean;
    fast?: boolean;
  }) {
    const raw = await apiFetch<Parameters<typeof mapBasketMultiGameTickets>[0]>(
      "/basket/superbet/multi-game/tickets",
      {
        method: "POST",
        body: JSON.stringify({
          event_ids: dto.eventIds,
          bankroll: dto.bankroll,
          stake: dto.stake,
          min_legs: dto.minLegs,
          max_legs: dto.maxLegs,
          max_tickets: dto.maxTickets,
          require_apostar: dto.requireApostar,
          fast: dto.fast ?? true,
        }),
        timeoutMs: 120_000,
      },
    );
    return mapBasketMultiGameTickets(raw);
  }

  async getBaseballSuperbetLive(dto?: { sportId?: number; allSports?: boolean }) {
    const params = new URLSearchParams();
    if (dto?.sportId != null) {
      params.set("sport_id", String(dto.sportId));
    }
    if (dto?.allSports) {
      params.set("all_sports", "true");
    }
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapBaseballSuperbetLiveFeed>[0]>(
      `/baseball/superbet/live${qs}`,
      { timeoutMs: API_SYNC_TIMEOUT_MS },
    );
    return mapBaseballSuperbetLiveFeed(raw);
  }

  async getBaseballSuperbetEvent(dto: { eventId: number; saveBronze?: boolean }) {
    const params = new URLSearchParams();
    if (dto.saveBronze === false) params.set("save_bronze", "false");
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapBaseballSuperbetEvent>[0]>(
      `/baseball/superbet/events/${dto.eventId}${qs}`,
      { timeoutMs: 30_000 },
    );
    return mapBaseballSuperbetEvent(raw);
  }

  async getBaseballSuperbetLiveAdvice(dto: {
    eventId: number;
    bankroll?: number;
    fast?: boolean;
    market?: string;
    outcome?: string;
    stake?: number;
    oddsPlaced?: number;
  }) {
    const params = new URLSearchParams();
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.fast) params.set("fast", "true");
    if (dto.market) params.set("market", dto.market);
    if (dto.outcome) params.set("outcome", dto.outcome);
    if (dto.stake != null) params.set("stake", String(dto.stake));
    if (dto.oddsPlaced != null) params.set("odds_placed", String(dto.oddsPlaced));
    const qs = params.size > 0 ? `?${params}` : "";
    const raw = await apiFetch<Parameters<typeof mapBaseballSuperbetLiveAdvice>[0]>(
      `/baseball/superbet/live/${dto.eventId}/advice${qs}`,
      { timeoutMs: dto.fast ? 60_000 : API_SYNC_TIMEOUT_MS },
    );
    return mapBaseballSuperbetLiveAdvice(raw);
  }

  async getLiveCopilot(dto: {
    eventId: number;
    sport: "football" | "basketball" | "baseball";
    phase?: string;
    bankroll?: number;
    fast?: boolean;
    kickoff?: string;
  }) {
    const params = new URLSearchParams();
    if (dto.bankroll != null) params.set("bankroll", String(dto.bankroll));
    if (dto.fast !== false) params.set("fast", "true");
    if (dto.phase) params.set("phase", dto.phase);
    if (dto.kickoff) params.set("kickoff", dto.kickoff);
    const qs = params.size > 0 ? `?${params}` : "";
    const base =
      dto.sport === "basketball"
        ? `/basket/superbet/live/${dto.eventId}/copilot`
        : dto.sport === "baseball"
          ? `/baseball/superbet/live/${dto.eventId}/copilot`
          : `/worldcup/superbet/live/${dto.eventId}/copilot`;
    const raw = await apiFetch<Parameters<typeof mapLiveCopilot>[0]>(`${base}${qs}`, {
      timeoutMs: 90_000,
    });
    return mapLiveCopilot(raw);
  }

  async postLiveCopilotAgent(dto: {
    eventId: number;
    sport: "football" | "basketball" | "baseball";
    message: string;
    history: import("@/domain/entities").LiveCopilotChatMessage[];
    phase?: string;
    bankroll?: number;
    fast?: boolean;
    kickoff?: string;
  }) {
    const base =
      dto.sport === "basketball"
        ? `/basket/superbet/live/${dto.eventId}/copilot/agent`
        : dto.sport === "baseball"
          ? `/baseball/superbet/live/${dto.eventId}/copilot/agent`
          : `/worldcup/superbet/live/${dto.eventId}/copilot/agent`;
    const raw = await apiFetch<Record<string, unknown>>(base, {
      method: "POST",
      body: JSON.stringify({
        message: dto.message,
        history: dto.history.map((m) => ({ role: m.role, content: m.content })),
        phase: dto.phase ?? "friendly",
        bankroll: dto.bankroll ?? 1000,
        fast: dto.fast !== false,
        kickoff: dto.kickoff ?? undefined,
      }),
      timeoutMs: 120_000,
    });
    return mapLiveCopilotAgent(raw);
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
