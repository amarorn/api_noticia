import type {
  INewsRepository,
  NewsAllParams,
  NewsCardsParams,
  NewsFeedParams,
  NewsSyncOptions,
} from "@/domain/repositories";

export class SyncNewsSourcesUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute(options?: NewsSyncOptions) {
    return this.repository.syncSources(options);
  }
}

export class GetNewsFeedUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute(params: NewsFeedParams = {}) {
    return this.repository.getFeed(params);
  }
}

export class GetNewsCardsUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute(params: NewsCardsParams = {}) {
    return this.repository.getCards(params);
  }
}

export class GetNewsAllUseCase {
  constructor(private readonly repository: INewsRepository) {}

  execute(params: NewsAllParams = {}) {
    return this.repository.getAll(params);
  }
}
