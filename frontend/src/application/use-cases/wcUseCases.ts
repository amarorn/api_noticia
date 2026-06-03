import type { IWcRepository } from "@/domain/repositories";
import type {
  WcGroupStandings,
  WcPrediction,
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
    return this.repository.predictMatch(dto.homeTeam, dto.awayTeam, dto.phase);
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
