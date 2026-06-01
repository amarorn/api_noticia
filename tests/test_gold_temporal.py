from datetime import datetime, timedelta, timezone

import pandas as pd

from pipelines.gold import filter_news_for_match


def test_filter_news_before_match():
    match_date = datetime(2024, 4, 13, 21, 0, tzinfo=timezone.utc)
    silver_df = pd.DataFrame([
        {
            "id": "1",
            "published_at": match_date - timedelta(days=2),
            "title": "ok",
        },
        {
            "id": "2",
            "published_at": match_date + timedelta(days=1),
            "title": "future",
        },
        {
            "id": "3",
            "published_at": match_date - timedelta(days=30),
            "title": "too old",
        },
    ])

    filtered = filter_news_for_match(silver_df, match_date, window_days=7)
    assert len(filtered) == 1
    assert filtered.iloc[0]["id"] == "1"
