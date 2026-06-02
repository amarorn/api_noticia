from __future__ import annotations

from pathlib import Path

import structlog

from config import settings

logger = structlog.get_logger()

LAYER_TABLES = {
    "bronze": "bronze_articles",
    "silver": "silver_articles",
    "gold": "gold_bolao_context",
    "fixtures": "fixtures_results",
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


def sync_layer(layer: str, write_disposition: str = "WRITE_APPEND") -> dict:
    layer_paths = {
        "bronze": settings.bronze_path,
        "silver": settings.silver_path,
        "gold": settings.gold_path,
        "fixtures": settings.fixtures_path,
    }
    local_dir = layer_paths.get(layer)
    if local_dir is None:
        raise ValueError(f"Camada inválida: {layer}")

    gcs_prefix = f"lake/{layer}"
    uploaded = upload_parquet_dir(local_dir, gcs_prefix)
    table = LAYER_TABLES[layer]

    for uri in uploaded:
        load_parquet_to_bigquery(uri, table, write_disposition=write_disposition)

    return {"layer": layer, "files": len(uploaded), "table": table}


def sync_all_layers() -> list[dict]:
    return [sync_layer(layer) for layer in LAYER_TABLES]
