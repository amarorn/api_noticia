from datetime import datetime, timezone
from hashlib import sha256

import feedparser
import httpx
import structlog
from bs4 import BeautifulSoup

from config import settings
from ingest.sources_loader import RSSSourceConfig, load_sources
from schemas.models import BronzeArticle

logger = structlog.get_logger()


def _content_hash(title: str, url: str) -> str:
    return sha256(f"{title}|{url}".encode()).hexdigest()


def _make_id(source: str, url: str) -> str:
    return sha256(f"{source}|{url}".encode()).hexdigest()[:16]


def _parse_published(entry: dict) -> datetime | None:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return None
    return datetime(*published[:6], tzinfo=timezone.utc)


async def _fetch_article_body(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        return "\n".join(paragraphs[:30]) if paragraphs else None
    except Exception as exc:
        logger.warning("fetch_body_failed", url=url, error=str(exc))
        return None


async def collect_rss_source(
    source_config: RSSSourceConfig,
    fetch_full_body: bool = False,
) -> list[BronzeArticle]:
    scraped_at = datetime.now(timezone.utc)

    async with httpx.AsyncClient(
        headers={"User-Agent": "SportsNewsLake/0.1 (research; +https://github.com/cactus)"},
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        try:
            response = await client.get(source_config.feed_url)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except Exception as exc:
            logger.error("rss_fetch_failed", source=source_config.name, error=str(exc))
            return []

        if feed.bozo and not feed.entries:
            logger.error("rss_parse_failed", source=source_config.name, error=str(feed.bozo_exception))
            return []

        articles: list[BronzeArticle] = []

        max_entries = settings.rss_max_entries_per_source
        if source_config.source.startswith("google_"):
            max_entries = min(max_entries, 100)
        for entry in feed.entries[:max_entries]:
            url = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not url or not title:
                continue

            summary = entry.get("summary") or entry.get("description")
            if summary and "<" in summary:
                summary = BeautifulSoup(summary, "lxml").get_text(strip=True)

            content_raw = None
            if fetch_full_body:
                content_raw = await _fetch_article_body(client, url)

            article = BronzeArticle(
                id=_make_id(source_config.source, url),
                source=source_config.source,
                source_url=url,
                title=title,
                summary=summary,
                content_raw=content_raw,
                published_at=_parse_published(entry),
                scraped_at=scraped_at,
                content_hash=_content_hash(title, url),
                raw_payload={
                    "feed_title": feed.feed.get("title"),
                    "entry_id": entry.get("id"),
                    "tags": [t.get("term") for t in entry.get("tags", []) if t.get("term")],
                },
            )
            articles.append(article)

    logger.info("rss_collected", source=source_config.name, count=len(articles))
    return articles


async def collect_all_sources(
    fetch_full_body: bool = False,
    sources: list[RSSSourceConfig] | None = None,
) -> list[BronzeArticle]:
    source_list = sources or load_sources()
    all_articles: list[BronzeArticle] = []
    for source_config in source_list:
        articles = await collect_rss_source(source_config, fetch_full_body=fetch_full_body)
        all_articles.extend(articles)
    logger.info("collection_complete", total=len(all_articles), sources=len(source_list))
    return all_articles
