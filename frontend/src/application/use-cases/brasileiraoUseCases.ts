import type { IBrasileiraoRepository } from "@/domain/repositories";

export class GetBrasileiraoRoundUseCase {
  constructor(private readonly repository: IBrasileiraoRepository) {}

  execute() {
    return this.repository.getRoundPredictions();
  }
}
