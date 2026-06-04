import type {
  INewsRepository,
  NewsAllParams,
  NewsCardsParams,
  NewsFeedParams,
  NewsSyncOptions,
} from "@/domain/repositories";
import {
  API_SYNC_FETCH_BODY_TIMEOUT_MS,
  API_SYNC_TIMEOUT_MS,
  apiFetch,
} from "../api/client";
import { mapNewsCards, mapNewsFeed, mapNewsSync } from "../mappers/newsMappers";

export class NewsApiRepository implements INewsRepository {
  async syncSources(options: NewsSyncOptions = {}) {
    const fetchBody = options.fetchBody ?? true;
    const fullRebuild = options.fullRebuild ?? false;
    const params = new URLSearchParams();
    if (fetchBody) params.set("fetch_body", "true");
    if (fullRebuild) params.set("full_rebuild", "true");
    const qs = params.toString();

    const raw = await apiFetch<Parameters<typeof mapNewsSync>[0]>(
      `/news/sync${qs ? `?${qs}` : ""}`,
      {
        method: "POST",
        timeoutMs: fetchBody ? API_SYNC_FETCH_BODY_TIMEOUT_MS : API_SYNC_TIMEOUT_MS,
      },
    );
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

  async getCards(params: NewsCardsParams = {}) {
    const search = new URLSearchParams();
    if (params.limit != null) search.set("limit", String(params.limit));
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.source) search.set("source", params.source);
    if (params.query) search.set("q", params.query);
    if (params.days != null) search.set("days", String(params.days));
    if (params.team) search.set("team", params.team);
    if (params.homeTeam) search.set("home_team", params.homeTeam);
    if (params.awayTeam) search.set("away_team", params.awayTeam);
    if (params.teams?.length) search.set("teams", params.teams.join(","));

    const qs = search.toString();
    const raw = await apiFetch<Parameters<typeof mapNewsCards>[0]>(
      `/news/cards${qs ? `?${qs}` : ""}`,
    );
    return mapNewsCards(raw);
  }

  async getAll(params: NewsAllParams = {}) {
    const search = new URLSearchParams();
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.source) search.set("source", params.source);
    if (params.query) search.set("q", params.query);
    if (params.days != null) search.set("days", String(params.days));
    if (params.team) search.set("team", params.team);
    if (params.homeTeam) search.set("home_team", params.homeTeam);
    if (params.awayTeam) search.set("away_team", params.awayTeam);
    if (params.teams?.length) search.set("teams", params.teams.join(","));

    const qs = search.toString();
    const raw = await apiFetch<Parameters<typeof mapNewsFeed>[0]>(
      `/news/all${qs ? `?${qs}` : ""}`,
    );
    return mapNewsFeed(raw);
  }
}

export const newsRepository = new NewsApiRepository();
