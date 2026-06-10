from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ingest.storage import load_bronze
from pipelines.silver import load_silver


def _to_string_series(series: pd.Series) -> pd.Series:
    return series.astype("string")


def _to_nullable_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _normalize_datetime_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], utc=True, errors="coerce")
    return out


def prepare_timestamps_for_bq_parquet(df: pd.DataFrame) -> pd.DataFrame:
    """BigQuery via Parquet/GCS aceita TIMESTAMP em microssegundos, não nanos."""
    if df.empty:
        return df

    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            series = pd.to_datetime(out[col], utc=True, errors="coerce")
            out[col] = series.astype("datetime64[us, UTC]")
    return out


def prepare_dataframe_for_bq(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_timestamps_for_bq_parquet(df)


def normalize_bronze_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in ("id", "source", "source_url", "title", "summary", "content_raw", "content_hash"):
        if col in out.columns:
            out[col] = _to_string_series(out[col])

    if "raw_payload" in out.columns:
        out["raw_payload"] = out["raw_payload"].map(_json_string)

    out = _normalize_datetime_columns(out, ["published_at", "scraped_at"])
    if "content_hash" in out.columns:
        out = out.drop_duplicates(subset=["content_hash"], keep="last")
    return prepare_timestamps_for_bq_parquet(out)


def normalize_silver_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in (
        "id",
        "source",
        "source_url",
        "title",
        "body",
        "summary",
        "content_hash",
    ):
        if col in out.columns:
            out[col] = _to_string_series(out[col])

    for col in ("teams_mentioned", "national_teams_mentioned", "players_mentioned", "categories"):
        if col in out.columns:
            out[col] = out[col].map(_json_string)

    out = _normalize_datetime_columns(out, ["published_at", "scraped_at"])
    if "event_id" in out.columns:
        out["event_id"] = _to_nullable_int_series(out["event_id"])
    dedup_col = "content_hash" if "content_hash" in out.columns else "id"
    return prepare_timestamps_for_bq_parquet(
        out.drop_duplicates(subset=[dedup_col], keep="last")
    )


def normalize_gold_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in out.select_dtypes(include=["object"]).columns:
        if col.endswith("_mentioned") or col in ("teams_mentioned", "national_teams_mentioned"):
            out[col] = out[col].map(_json_string)
        elif out[col].map(lambda x: isinstance(x, (dict, list))).any():
            out[col] = out[col].map(_json_string)
        else:
            out[col] = _to_string_series(out[col])

    out = _normalize_datetime_columns(
        out,
        [c for c in out.columns if "date" in c.lower() or c.endswith("_at")],
    )
    for col in (
        "event_id",
        "round_number",
        "season",
        "home_score",
        "away_score",
        "sofa_stats_available",
    ):
        if col in out.columns:
            out[col] = _to_nullable_int_series(out[col])
    return prepare_timestamps_for_bq_parquet(out)


def _json_default(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return str(value)


def _json_string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=_json_default)
    except TypeError:
        return str(value)


def load_bronze_articles_df() -> pd.DataFrame:
    return normalize_bronze_df(load_bronze())


def load_silver_articles_df() -> pd.DataFrame:
    return normalize_silver_df(load_silver())


def load_gold_articles_df() -> pd.DataFrame:
    from models.dataset import load_gold_dataset

    return normalize_gold_df(load_gold_dataset())


def load_layer_dataframe(layer: str) -> pd.DataFrame:
    loaders = {
        "bronze": load_bronze_articles_df,
        "silver": load_silver_articles_df,
        "gold": load_gold_articles_df,
    }
    loader = loaders.get(layer)
    if loader is None:
        raise ValueError(f"Camada sem consolidador dataframe: {layer}")
    return loader()
