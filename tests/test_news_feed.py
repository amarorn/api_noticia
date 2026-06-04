from datetime import datetime, timezone

import pandas as pd

from pipelines.news_feed import (
    MAX_NEWS_ALL,
    build_news_all,
    build_news_cards,
    build_news_feed,
    sentiment_label,
)


def test_sentiment_label_thresholds():
    assert sentiment_label(0.5) == "positive"
    assert sentiment_label(-0.5) == "negative"
    assert sentiment_label(0.0) == "neutral"
    assert sentiment_label(None) == "neutral"


def test_build_news_feed_filters_and_sorts():
    now = datetime.now(timezone.utc)
    df = pd.DataFrame(
        [
            {
                "id": "a1",
                "source": "espn_br",
                "source_url": "https://espn.com/1",
                "title": "Flamengo vence clássico",
                "body": "Vitória importante do Flamengo",
                "summary": None,
                "published_at": now,
                "scraped_at": now,
                "content_hash": "h1",
                "teams_mentioned": ["Flamengo"],
                "sentiment_score": 0.5,
            },
            {
                "id": "a2",
                "source": "globo_esporte",
                "source_url": "https://ge.globo.com/2",
                "title": "Palmeiras em crise",
                "body": "Derrota preocupa torcida",
                "summary": None,
                "published_at": now,
                "scraped_at": now,
                "content_hash": "h2",
                "teams_mentioned": ["Palmeiras"],
                "sentiment_score": -0.5,
            },
        ]
    )

    result = build_news_feed(df, limit=10, source="espn_br", query="flamengo")
    assert result["total"] == 1
    assert len(result["articles"]) == 1
    assert result["articles"][0]["title"] == "Flamengo vence clássico"
    assert result["articles"][0]["sentiment_label"] == "positive"


def test_build_news_cards_filters_by_teams():
    now = datetime.now(timezone.utc)
    df = pd.DataFrame(
        [
            {
                "id": "n1",
                "source": "globo_esporte",
                "source_url": "https://ge.globo.com/1",
                "title": "Brasil convoca reforços",
                "body": "Seleção brasileira se prepara",
                "published_at": now,
                "scraped_at": now,
                "national_teams_mentioned": ["Brasil"],
                "teams_mentioned": [],
            },
            {
                "id": "n2",
                "source": "espn_br",
                "source_url": "https://espn.com/2",
                "title": "Flamengo treina",
                "body": "Clube carioca",
                "published_at": now,
                "scraped_at": now,
                "teams_mentioned": ["Flamengo"],
            },
        ]
    )
    result = build_news_cards(df, home_team="Brasil", away_team="Marrocos", limit=10)
    assert result["total"] == 1
    assert len(result["cards"]) == 1
    assert result["cards"][0]["id"] == "n1"
    assert "Brasil" in result["teams"]


def test_build_news_all_returns_every_row():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": f"n{i}",
            "source": "espn_br",
            "source_url": f"https://espn.com/{i}",
            "title": f"Notícia {i}",
            "body": "texto",
            "published_at": now,
            "scraped_at": now,
        }
        for i in range(5)
    ]
    df = pd.DataFrame(rows)
    result = build_news_all(df)
    assert result["total"] == 5
    assert len(result["articles"]) == 5
