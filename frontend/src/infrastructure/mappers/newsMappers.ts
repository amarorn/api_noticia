import type {
  NewsArticle,
  NewsCards,
  NewsFeed,
  NewsSentimentLabel,
  NewsSyncResult,
} from "@/domain/entities";

interface ApiNewsArticle {
  id: string;
  source: string;
  source_name: string;
  source_url: string;
  title: string;
  summary: string | null;
  body_preview: string;
  published_at: string | null;
  scraped_at: string | null;
  teams_mentioned: string[];
  categories: string[];
  sentiment_score: number | null;
  sentiment_label: string;
}

interface ApiNewsFeed {
  total: number;
  limit: number;
  offset: number;
  sources: Array<{ id: string; name: string; count: number }>;
  articles: ApiNewsArticle[];
}

function mapSentiment(label: string): NewsSentimentLabel {
  if (label === "positive" || label === "negative") return label;
  return "neutral";
}

function mapArticle(raw: ApiNewsArticle): NewsArticle {
  return {
    id: raw.id,
    source: raw.source,
    sourceName: raw.source_name,
    sourceUrl: raw.source_url,
    title: raw.title,
    summary: raw.summary,
    bodyPreview: raw.body_preview,
    publishedAt: raw.published_at,
    scrapedAt: raw.scraped_at,
    teamsMentioned: raw.teams_mentioned ?? [],
    categories: raw.categories ?? [],
    sentimentScore: raw.sentiment_score,
    sentimentLabel: mapSentiment(raw.sentiment_label),
  };
}

interface ApiNewsSync {
  collected: number;
  by_source: Record<string, number>;
  silver_updated: boolean;
  articles_silver: number;
  synced_at: string;
}

export function mapNewsSync(raw: ApiNewsSync): NewsSyncResult {
  return {
    collected: raw.collected,
    bySource: raw.by_source ?? {},
    silverUpdated: raw.silver_updated,
    articlesSilver: raw.articles_silver,
    syncedAt: raw.synced_at,
  };
}

export function mapNewsFeed(raw: ApiNewsFeed): NewsFeed {
  return {
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
    sources: raw.sources.map((s) => ({
      id: s.id,
      name: s.name,
      count: s.count,
    })),
    articles: raw.articles.map(mapArticle),
  };
}

interface ApiNewsCards {
  total: number;
  limit: number;
  offset: number;
  teams: string[];
  cards: ApiNewsArticle[];
}

export function mapNewsCards(raw: ApiNewsCards): NewsCards {
  return {
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
    teams: raw.teams ?? [],
    cards: raw.cards.map(mapArticle),
  };
}
