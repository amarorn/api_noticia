import type { IWcRepository } from "@/domain/repositories";
import type { WcPrediction, WcRound } from "@/domain/entities";
import type { WcPredictRequestDto } from "../dtos";

export class GetWcRoundUseCase {
  constructor(private readonly repository: IWcRepository) {}

  execute(): Promise<WcRound> {
    return this.repository.getRound();
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
