from __future__ import annotations

import io
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.gcp.medallion import MEDALLION_TABLES, gcs_snapshot_blob
from ingest.gcp.sync import (
    _ensure_adc,
    load_parquet_to_bigquery,
    sync_layer,
    upload_parquet_file,
)
from ingest.gcp.lake_frames import prepare_dataframe_for_bq
from ingest.sofascore.paths import MATCH_ENRICH_PARQUET, MATCH_STATS_PARQUET

logger = structlog.get_logger()

LAYER_SNAPSHOT_FILES: dict[str, str] = {
    "bronze": "articles.parquet",
    "silver": "articles.parquet",
    "gold": "articles.parquet",
    "silver_sofascore": MATCH_STATS_PARQUET,
    "silver_sofascore_enrich": MATCH_ENRICH_PARQUET,
    "silver_fixtures": "world_cup_fixtures.parquet",
    "bronze_sofascore": "events.parquet",
    "gold_wc": "match_features.parquet",
}


def cloud_lake_enabled() -> bool:
    return settings.lake_primary == "cloud" and bool(settings.gcs_bucket)


def _gcs_client():
    _ensure_adc()
    from google.cloud import storage

    return storage.Client(project=settings.gcp_project)


def read_layer_snapshot(layer: str, *, filename: str | None = None) -> pd.DataFrame:
    if not cloud_lake_enabled():
        return pd.DataFrame()

    blob_name = gcs_snapshot_blob(layer, filename or LAYER_SNAPSHOT_FILES[layer])
    client = _gcs_client()
    bucket = client.bucket(settings.gcs_bucket)
    blob = bucket.blob(blob_name)
    if not blob.exists():
        logger.debug("gcs_snapshot_missing", layer=layer, blob=blob_name)
        return pd.DataFrame()

    data = blob.download_as_bytes()
    df = pd.read_parquet(io.BytesIO(data))
    logger.debug("gcs_snapshot_read", layer=layer, blob=blob_name, rows=len(df))
    return df


def upload_snapshot_parquet(
    df: pd.DataFrame,
    layer: str,
    *,
    filename: str | None = None,
) -> str:
    import tempfile
    from pathlib import Path

    if df is None or df.empty:
        return ""

    fname = filename or LAYER_SNAPSHOT_FILES[layer]
    blob = gcs_snapshot_blob(layer, fname)
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        prepare_dataframe_for_bq(df).to_parquet(tmp_path, index=False)
        return upload_parquet_file(tmp_path, blob)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_layer_snapshot(
    layer: str,
    df: pd.DataFrame,
    *,
    filename: str | None = None,
    sync_bq: bool | None = None,
) -> str:
    if not cloud_lake_enabled():
        raise RuntimeError("GCS lake não configurado (LAKE_PRIMARY=cloud + GCS_BUCKET)")

    if df is None or df.empty:
        logger.warning("gcs_snapshot_skip", layer=layer, reason="empty")
        return ""

    do_bq = settings.lake_sync_bq_on_write if sync_bq is None else sync_bq
    uri = upload_snapshot_parquet(df, layer, filename=filename)
    if uri and do_bq:
        load_parquet_to_bigquery(
            uri,
            MEDALLION_TABLES[layer],
            write_disposition="WRITE_TRUNCATE",
        )
    if uri:
        logger.info("gcs_snapshot_written", layer=layer, uri=uri, rows=len(df), bq=do_bq)
    return uri


def layer_fingerprint(layer: str) -> str:
    import hashlib

    if not cloud_lake_enabled():
        return "local"

    blob_name = gcs_snapshot_blob(layer, LAYER_SNAPSHOT_FILES[layer])
    client = _gcs_client()
    blob = client.bucket(settings.gcs_bucket).blob(blob_name)
    if not blob.exists():
        return "empty"
    blob.reload()
    payload = f"{blob_name}:{blob.updated}:{blob.size}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def publish_layer(layer: str, *, sync_bq: bool = True) -> dict[str, Any]:
    """Republica snapshot consolidado no GCS (+ BQ) a partir do lake local."""
    result = sync_layer(layer, write_disposition="WRITE_TRUNCATE")
    if sync_bq:
        return result
    return result
