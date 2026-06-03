import pandas as pd

from pipelines.silver import _extract_entities, _simple_sentiment, bronze_to_silver


def test_extract_teams():
    text = "Flamengo vence Palmeiras no Maracanã"
    teams, _ = _extract_entities(text)
    assert "Flamengo" in teams
    assert "Palmeiras" in teams


def test_sentiment_positive():
    score = _simple_sentiment("Flamengo garante vitória e se aproxima da liderança")
    assert score > 0


def test_sentiment_negative():
    score = _simple_sentiment("Time entra em crise após derrota e risco de rebaixamento")
    assert score < 0


def test_bronze_to_silver_accepts_nan_published_at():
    df = pd.DataFrame(
        [
            {
                "id": "x1",
                "source": "espn_br",
                "source_url": "https://espn.com.br/a",
                "title": "Flamengo em campo",
                "content_raw": None,
                "summary": None,
                "published_at": float("nan"),
                "scraped_at": "2026-06-03T12:00:00+00:00",
                "content_hash": "abc",
                "raw_payload": {},
            }
        ]
    )
    articles = bronze_to_silver(df)
    assert len(articles) == 1
    assert articles[0].published_at is None
