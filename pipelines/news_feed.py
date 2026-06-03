from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from ingest.sources_loader import load_sources

SENTIMENT_POSITIVE = 0.2
SENTIMENT_NEGATIVE = -0.2
BODY_PREVIEW_LEN = 280


def _source_name_map() -> dict[str, str]:
    try:
        return {s.source: s.name for s in load_sources()}
    except FileNotFoundError:
        return {}


def sentiment_label(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score > SENTIMENT_POSITIVE:
        return "positive"
    if score < SENTIMENT_NEGATIVE:
        return "negative"
    return "neutral"


def _parse_datetime(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        dt = pd.to_datetime(value, utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except Exception:
        return None


def _sort_key(row: pd.Series) -> datetime:
    for col in ("published_at", "scraped_at"):
        dt = _parse_datetime(row.get(col))
        if dt is not None:
            return dt
    return datetime.min.replace(tzinfo=timezone.utc)


def _body_preview(row: pd.Series) -> str:
    text = row.get("summary") or row.get("body") or row.get("title") or ""
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.split())
    if len(text) <= BODY_PREVIEW_LEN:
        return text
    return text[:BODY_PREVIEW_LEN].rsplit(" ", 1)[0] + "…"


def _teams_list(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(t) for t in value if t]
    return []


def build_news_feed(
    silver_df: pd.DataFrame,
    *,
    limit: int = 24,
    offset: int = 0,
    source: str | None = None,
    query: str | None = None,
    days: int | None = 30,
) -> dict[str, Any]:
    source_names = _source_name_map()
    empty = {
        "total": 0,
        "limit": limit,
        "offset": offset,
        "sources": [],
        "articles": [],
    }

    if silver_df.empty:
        return empty

    df = silver_df.copy()

    if source:
        df = df[df["source"] == source]

    if days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        dates = df.apply(_sort_key, axis=1)
        df = df[dates >= cutoff]

    if query:
        q = query.strip().lower()
        if q:
            searchable = (
                df["title"].fillna("").astype(str)
                + " "
                + df.get("summary", pd.Series([""] * len(df))).fillna("").astype(str)
                + " "
                + df.get("body", pd.Series([""] * len(df))).fillna("").astype(str)
            ).str.lower()
            df = df[searchable.str.contains(q, regex=False)]

    df = df.copy()
    df["_sort_dt"] = df.apply(_sort_key, axis=1)
    df = df.sort_values("_sort_dt", ascending=False)

    source_counts = df.groupby("source").size().to_dict() if not df.empty else {}
    sources_meta = [
        {
            "id": sid,
            "name": source_names.get(sid, sid.replace("_", " ").title()),
            "count": int(count),
        }
        for sid, count in sorted(source_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    total = len(df)
    page = df.iloc[offset : offset + limit]

    articles = []
    for _, row in page.iterrows():
        sentiment = row.get("sentiment_score")
        if sentiment is not None and not pd.isna(sentiment):
            sentiment = float(sentiment)
        else:
            sentiment = None

        published = _parse_datetime(row.get("published_at"))
        scraped = _parse_datetime(row.get("scraped_at"))
        sid = str(row.get("source", ""))

        articles.append(
            {
                "id": str(row.get("id", "")),
                "source": sid,
                "source_name": source_names.get(sid, sid.replace("_", " ").title()),
                "source_url": str(row.get("source_url", "")),
                "title": str(row.get("title", "")),
                "summary": row.get("summary") if pd.notna(row.get("summary")) else None,
                "body_preview": _body_preview(row),
                "published_at": published.isoformat() if published else None,
                "scraped_at": scraped.isoformat() if scraped else None,
                "teams_mentioned": _teams_list(row.get("teams_mentioned")),
                "national_teams_mentioned": _teams_list(row.get("national_teams_mentioned")),
                "categories": _teams_list(row.get("categories")),
                "sentiment_score": sentiment,
                "sentiment_label": sentiment_label(sentiment),
            }
        )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sources": sources_meta,
        "articles": articles,
    }
