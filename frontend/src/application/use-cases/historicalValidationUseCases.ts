import type {
  IHistoricalValidationRepository,
  ValidateHistoricalMatchRequest,
} from "@/domain/repositories";

export class GetWcEditionsUseCase {
  constructor(private readonly repository: IHistoricalValidationRepository) {}

  execute() {
    return this.repository.getEditions();
  }
}

export class GetWcEditionMatchesUseCase {
  constructor(private readonly repository: IHistoricalValidationRepository) {}

  execute(season: number) {
    return this.repository.getEditionMatches(season);
  }
}

export class ValidateHistoricalMatchUseCase {
  constructor(private readonly repository: IHistoricalValidationRepository) {}

  execute(request: ValidateHistoricalMatchRequest) {
    return this.repository.validateMatch(request);
  }
}
