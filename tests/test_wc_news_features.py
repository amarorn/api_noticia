from datetime import datetime, timedelta, timezone

import pandas as pd

from pipelines.wc_news_features import NEWS_FEATURE_NAMES, wc_news_feature_vector


def test_wc_news_features_neutral_without_silver():
    vec = wc_news_feature_vector("Brasil", "Argentina", silver_df=pd.DataFrame())
    assert vec == [0.0, 0.0, 0.0]
    assert len(NEWS_FEATURE_NAMES) == 3


def test_wc_news_count_and_sentiment_diff():
    now = datetime.now(timezone.utc)
    silver = pd.DataFrame(
        [
            {
                "id": "1",
                "published_at": now - timedelta(days=2),
                "scraped_at": now,
                "national_teams_mentioned": ["Brasil"],
                "teams_mentioned": [],
                "sentiment_score": 0.5,
            },
            {
                "id": "2",
                "published_at": now - timedelta(days=1),
                "scraped_at": now,
                "national_teams_mentioned": ["Argentina"],
                "teams_mentioned": [],
                "sentiment_score": -0.5,
            },
        ]
    )
    vec = wc_news_feature_vector("Brasil", "Argentina", before_date=now, silver_df=silver)
    assert vec[2] == 1.0
    assert vec[0] == 0.0
    assert vec[1] == 1.0
