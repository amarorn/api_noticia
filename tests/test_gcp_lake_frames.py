import pandas as pd

from ingest.gcp.lake_frames import normalize_bronze_df, prepare_timestamps_for_bq_parquet


def test_normalize_bronze_df_unifies_content_raw_as_string():
    df = pd.DataFrame(
        [
            {"id": "1", "content_hash": "a", "content_raw": None, "scraped_at": "2026-06-01T00:00:00Z"},
            {"id": "2", "content_hash": "b", "content_raw": "texto", "scraped_at": "2026-06-02T00:00:00Z"},
        ]
    )
    out = normalize_bronze_df(df)
    assert str(out["content_raw"].dtype) == "string"
    assert out.iloc[1]["content_raw"] == "texto"


def test_prepare_timestamps_for_bq_parquet_uses_microseconds():
    df = pd.DataFrame(
        {
            "scraped_at": pd.to_datetime(["2026-06-01T12:00:00Z"], utc=True),
            "published_at": pd.to_datetime(["2026-06-01T10:00:00Z"], utc=True),
        }
    )
    out = prepare_timestamps_for_bq_parquet(df)
    assert str(out["scraped_at"].dtype) == "datetime64[us, UTC]"
