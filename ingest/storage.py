from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import structlog

from config import settings
from schemas.models import BronzeArticle

logger = structlog.get_logger()


def _partition_path(layer: Path, source: str, dt: datetime | None = None) -> Path:
    dt = dt or datetime.now(timezone.utc)
    return layer / f"source={source}" / f"year={dt.year}" / f"month={dt.month:02d}" / f"day={dt.day:02d}"


def save_bronze(articles: list[BronzeArticle]) -> Path:
    if not articles:
        logger.warning("no_articles_to_save")
        return settings.bronze_path

    from ingest.gcp.lake_store import cloud_lake_enabled, write_layer_snapshot
    from ingest.gcp.lake_frames import normalize_bronze_df

    if cloud_lake_enabled():
        records = [a.model_dump(mode="json") for a in articles]
        new_df = pd.DataFrame(records)
        existing = load_bronze()
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["content_hash"], keep="last")
        write_layer_snapshot("bronze", normalize_bronze_df(combined))
        logger.info("bronze_saved_cloud", rows=len(combined))
        return settings.bronze_path

    settings.bronze_path.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []

    by_source: dict[str, list[BronzeArticle]] = {}
    for article in articles:
        by_source.setdefault(article.source, []).append(article)

    for source, source_articles in by_source.items():
        partition = _partition_path(settings.bronze_path, source)
        partition.mkdir(parents=True, exist_ok=True)

        records = [a.model_dump(mode="json") for a in source_articles]
        df = pd.DataFrame(records)

        existing_files = list(partition.glob("*.parquet"))
        if existing_files:
            existing_df = pd.concat([pd.read_parquet(f) for f in existing_files], ignore_index=True)
            df = pd.concat([existing_df, df], ignore_index=True)
            df = df.drop_duplicates(subset=["content_hash"], keep="last")

        timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
        out_path = partition / f"articles_{timestamp}.parquet"
        df.to_parquet(out_path, index=False)
        saved_paths.append(out_path)
        logger.info("bronze_saved", path=str(out_path), rows=len(df))

    return saved_paths[0]


def load_bronze(source: str | None = None) -> pd.DataFrame:
    from ingest.gcp.lake_store import cloud_lake_enabled, read_layer_snapshot
    from ingest.gcp.lake_frames import normalize_bronze_df

    if cloud_lake_enabled():
        df = normalize_bronze_df(read_layer_snapshot("bronze"))
        if source and not df.empty:
            df = df[df["source"] == source]
        return df.reset_index(drop=True)

    bronze_root = settings.bronze_path
    if not bronze_root.exists():
        return pd.DataFrame()

    pattern = f"source={source}/**/*.parquet" if source else "**/*.parquet"
    files = list(bronze_root.glob(pattern))
    if not files:
        return pd.DataFrame()

    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    return df.drop_duplicates(subset=["content_hash"], keep="last")
