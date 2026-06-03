import type { IHealthRepository } from "@/domain/repositories";

export class GetHealthUseCase {
  constructor(private readonly repository: IHealthRepository) {}

  execute() {
    return this.repository.getHealth();
  }
}
