import type { INewsRepository, NewsFeedParams } from "@/domain/repositories";

export class SyncNewsSourcesUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute() {
    return this.repository.syncSources();
  }
}

export class GetNewsFeedUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute(params: NewsFeedParams = {}) {
    return this.repository.getFeed(params);
  }
}
