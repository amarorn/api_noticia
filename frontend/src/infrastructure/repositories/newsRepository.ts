import type { INewsRepository, NewsFeedParams } from "@/domain/repositories";
import { API_SYNC_TIMEOUT_MS, apiFetch } from "../api/client";
import { mapNewsFeed, mapNewsSync } from "../mappers/newsMappers";

export class NewsApiRepository implements INewsRepository {
  async syncSources() {
    const raw = await apiFetch<Parameters<typeof mapNewsSync>[0]>("/news/sync", {
      method: "POST",
      timeoutMs: API_SYNC_TIMEOUT_MS,
    });
    return mapNewsSync(raw);
  }

  async getFeed(params: NewsFeedParams = {}) {
    const search = new URLSearchParams();
    if (params.limit != null) search.set("limit", String(params.limit));
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.source) search.set("source", params.source);
    if (params.query) search.set("q", params.query);
    if (params.days != null) search.set("days", String(params.days));

    const qs = search.toString();
    const raw = await apiFetch<Parameters<typeof mapNewsFeed>[0]>(
      `/news/feed${qs ? `?${qs}` : ""}`,
    );
    return mapNewsFeed(raw);
  }
}

export const newsRepository = new NewsApiRepository();
