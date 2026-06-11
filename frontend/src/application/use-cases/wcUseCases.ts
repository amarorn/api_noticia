import type { IWcRepository } from "@/domain/repositories";
import type {
  SofascoreResolvedEvent,
  WcCornersPrediction,
  WcFriendlies,
  WcGroupStandings,
  WcPrediction,
  WcSimulation,
  WcRound,
  WcSchedule,
  WcSquadDetail,
  WcSquadsIndex,
  UserOpenBetsList,
} from "@/domain/entities";
import type { WcPredictRequestDto } from "../dtos";

export class GetWcRoundUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(matchday?: number): Promise<WcRound> {
    return this.repository.getRound(matchday);
  }
}

export class GetWcScheduleUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<WcSchedule> {
    return this.repository.getSchedule();
  }
}

export class GetWcSquadsIndexUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<WcSquadsIndex> {
    return this.repository.getSquadsIndex();
  }
}

export class GetWcSquadUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(team: string): Promise<WcSquadDetail> {
    return this.repository.getSquad(team);
  }
}

export class PredictWcMatchUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: WcPredictRequestDto): Promise<WcPrediction> {
    return this.repository.predictMatch(dto);
  }
}

export class PredictWcCornersUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
  }): Promise<WcCornersPrediction> {
    return this.repository.predictCorners(dto);
  }
}

export class PredictWcInPlayUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    homeTeam: string;
    awayTeam: string;
    homeScore: number;
    awayScore: number;
    minute: number;
    phase?: string;
    matchMinutes?: number;
    superbetEventId?: number;
  }) {
    return this.repository.predictInPlay(dto);
  }
}

export class ResolveSofascoreEventUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    homeTeam: string;
    awayTeam: string;
    date: string;
  }): Promise<SofascoreResolvedEvent> {
    return this.repository.resolveSofascoreEvent(dto);
  }
}

export class GetWcTeamsUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<string[]> {
    return this.repository.getTeams();
  }
}

export class GetValueBetsUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute() {
    return this.repository.getValueBets();
  }
}

export class GetWcGroupStandingsUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<WcGroupStandings> {
    return this.repository.getGroupStandings();
  }
}

export class GetWcFriendliesUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    team: string;
    includeFinished?: boolean;
    includeUpcoming?: boolean;
  }): Promise<WcFriendlies> {
    return this.repository.getFriendlies(dto);
  }
}

export class GetSuperbetLiveUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto?: { sportId?: number; allSports?: boolean }) {
    return this.repository.getSuperbetLive(dto);
  }
}

export class GetSuperbetLiveAdviceUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    eventId: number;
    phase?: string;
    bankroll?: number;
    market?: string;
    outcome?: string;
    stake?: number;
    oddsPlaced?: number;
  }) {
    return this.repository.getSuperbetLiveAdvice(dto);
  }
}

export class GetSuperbetEventUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: { eventId: number; saveBronze?: boolean }) {
    return this.repository.getSuperbetEvent(dto);
  }
}

export class SimulateWcMatchUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(dto: {
    homeTeam: string;
    awayTeam: string;
    phase: string;
    matchDate?: string;
    fifaMatchId?: string;
    sofascoreEventId?: number;
  }): Promise<WcSimulation> {
    return this.repository.simulateMatch(dto);
  }
}

export class GetUserOpenBetsUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<UserOpenBetsList> {
    return this.repository.getUserOpenBets();
  }
}
