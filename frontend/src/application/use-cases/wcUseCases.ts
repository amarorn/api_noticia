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
