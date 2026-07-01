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


def test_load_silver_ignores_inplay_parquet(tmp_path, monkeypatch):
    """load_silver não deve ler silver/inplay/match_states.parquet."""
    from config import settings
    from pipelines.silver import load_silver, save_silver
    from schemas.models import SilverArticle

    monkeypatch.setattr(settings, "lake_root", tmp_path / "lake")
    monkeypatch.setattr("ingest.gcp.lake_store.cloud_lake_enabled", lambda: False)

    inplay = tmp_path / "lake" / "silver" / "inplay"
    inplay.mkdir(parents=True)
    (inplay / "match_states.parquet").write_bytes(b"not-a-parquet")

    article = SilverArticle(
        id="a1",
        source="espn_br",
        source_url="https://example.com/a",
        title="Brasil vence",
        body="texto",
        scraped_at="2026-06-03T12:00:00+00:00",
        content_hash="hash1",
    )
    save_silver([article])

    df = load_silver()
    assert len(df) == 1
    assert df.iloc[0]["id"] == "a1"

