from __future__ import annotations

from pathlib import Path

import structlog

from config import settings
from ingest.sofascore.paths import MATCH_STATS_PARQUET

logger = structlog.get_logger()

LAYER_TABLES = {
    "bronze": "bronze_articles",
    "silver": "silver_articles",
    "gold": "gold_bolao_context",
    "fixtures": "fixtures_results",
    "sofascore": "sofascore_match_stats",
}


def _require_gcp() -> None:
    if not settings.gcp_project:
        raise ValueError("Defina GCP_PROJECT no .env")
    if not settings.gcs_bucket:
        raise ValueError("Defina GCS_BUCKET no .env")


def upload_parquet_dir(local_dir: Path, gcs_prefix: str) -> list[str]:
    _require_gcp()
    from google.cloud import storage

    client = storage.Client(project=settings.gcp_project)
    bucket = client.bucket(settings.gcs_bucket)
    uploaded: list[str] = []

    if not local_dir.exists():
        logger.warning("gcs_upload_skip", path=str(local_dir), reason="missing")
        return uploaded

    for path in local_dir.rglob("*.parquet"):
        blob_name = f"{gcs_prefix}/{path.relative_to(local_dir).as_posix()}"
        bucket.blob(blob_name).upload_from_filename(str(path))
        uploaded.append(f"gs://{settings.gcs_bucket}/{blob_name}")
        logger.info("gcs_uploaded", blob=blob_name)

    return uploaded


def load_parquet_to_bigquery(
    gcs_uri: str,
    table_id: str,
    write_disposition: str = "WRITE_APPEND",
) -> None:
    _require_gcp()
    from google.cloud import bigquery

    client = bigquery.Client(project=settings.gcp_project)
    table_ref = f"{settings.gcp_project}.{settings.bq_dataset}.{table_id}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=write_disposition,
        autodetect=True,
    )
    job = client.load_table_from_uri(gcs_uri, table_ref, job_config=job_config)
    job.result()
    logger.info("bq_loaded", table=table_ref, source=gcs_uri)


def upload_parquet_file(local_path: Path, gcs_blob: str) -> str:
    _require_gcp()
    from google.cloud import storage

    if not local_path.is_file():
        logger.warning("gcs_upload_skip", path=str(local_path), reason="missing")
        return ""

    client = storage.Client(project=settings.gcp_project)
    bucket = client.bucket(settings.gcs_bucket)
    bucket.blob(gcs_blob).upload_from_filename(str(local_path))
    uri = f"gs://{settings.gcs_bucket}/{gcs_blob}"
    logger.info("gcs_uploaded", blob=gcs_blob)
    return uri


def sync_layer(layer: str, write_disposition: str = "WRITE_APPEND") -> dict:
    layer_paths = {
        "bronze": settings.bronze_path,
        "silver": settings.silver_path,
        "gold": settings.gold_path,
        "fixtures": settings.fixtures_path,
    }
    table = LAYER_TABLES[layer]
    uploaded: list[str] = []

    if layer == "sofascore":
        parquet_path = settings.sofascore_stats_dir / MATCH_STATS_PARQUET
        uri = upload_parquet_file(parquet_path, f"lake/sofascore/{MATCH_STATS_PARQUET}")
        if uri:
            uploaded.append(uri)
    else:
        local_dir = layer_paths.get(layer)
        if local_dir is None:
            raise ValueError(f"Camada inválida: {layer}")
        uploaded = upload_parquet_dir(local_dir, f"lake/{layer}")

    for uri in uploaded:
        load_parquet_to_bigquery(uri, table, write_disposition=write_disposition)

    return {"layer": layer, "files": len(uploaded), "table": table}


def sync_all_layers() -> list[dict]:
    return [sync_layer(layer) for layer in LAYER_TABLES]
