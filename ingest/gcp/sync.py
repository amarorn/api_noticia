from __future__ import annotations

import os
from pathlib import Path

import structlog

from config import settings
from ingest.gcp.medallion import (
    MEDALLION_TABLES,
    SYNC_LAYER_ORDER,
    gcs_snapshot_blob,
    resolve_layer,
)
from ingest.gcp.lake_frames import load_layer_dataframe, prepare_dataframe_for_bq
from ingest.sofascore.bronze_dataset import load_bronze_sofascore_events
from ingest.sofascore.paths import MATCH_ENRICH_PARQUET, MATCH_STATS_PARQUET
from pipelines.wc_sofascore_features import build_gold_wc_match_features_df

logger = structlog.get_logger()

LAYER_TABLES = MEDALLION_TABLES


def _ensure_adc() -> None:
    creds = settings.google_application_credentials
    if creds is not None:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            str(creds.expanduser().resolve()),
        )


def _require_gcp() -> None:
    _ensure_adc()
    if not settings.gcp_project:
        raise ValueError("Defina GCP_PROJECT no .env")


def _require_gcs() -> None:
    _require_gcp()
    if not settings.gcs_bucket:
        raise ValueError("Defina GCS_BUCKET no .env ou use carga direta (sem bucket)")


def _table_ref(table_id: str) -> str:
    return f"{settings.gcp_project}.{settings.bq_dataset}.{table_id}"


def upload_parquet_dir(local_dir: Path, gcs_prefix: str) -> list[str]:
    _require_gcs()
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
    _require_gcs()
    from google.cloud import bigquery

    client = bigquery.Client(project=settings.gcp_project)
    table_ref = _table_ref(table_id)

    if write_disposition == "WRITE_TRUNCATE":
        client.delete_table(table_ref, not_found_ok=True)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        autodetect=True,
        schema_update_options=[
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
        ],
    )
    job = client.load_table_from_uri(gcs_uri, table_ref, job_config=job_config)
    job.result()
    logger.info("bq_loaded", table=table_ref, source=gcs_uri)


def load_dataframe_via_gcs(
    df,
    layer: str,
    table_id: str,
    *,
    filename: str = "snapshot.parquet",
    write_disposition: str = "WRITE_APPEND",
) -> tuple[int, str]:
    import tempfile

    if df is None or df.empty:
        logger.warning("gcs_dataframe_skip", layer=layer, reason="empty")
        return 0, ""

    blob = gcs_snapshot_blob(layer, filename)
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        prepare_dataframe_for_bq(df).to_parquet(tmp_path, index=False)
        uri = upload_parquet_file(tmp_path, blob)
        if not uri:
            return 0, ""
        load_parquet_to_bigquery(uri, table_id, write_disposition=write_disposition)
        return 1, uri
    finally:
        tmp_path.unlink(missing_ok=True)


def load_dataframe_to_bigquery(
    df,
    table_id: str,
    *,
    write_disposition: str = "WRITE_APPEND",
) -> int:
    _require_gcp()
    from google.cloud import bigquery

    if df is None or df.empty:
        logger.warning("bq_dataframe_skip", table=table_id, reason="empty")
        return 0

    client = bigquery.Client(project=settings.gcp_project)
    table_ref = _table_ref(table_id)

    if write_disposition == "WRITE_TRUNCATE":
        client.delete_table(table_ref, not_found_ok=True)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        autodetect=True,
        schema_update_options=[
            bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
        ],
    )
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()
    logger.info("bq_loaded_dataframe", table=table_ref, rows=len(df))
    return 1


def load_local_parquet_to_bigquery(
    local_paths: list[Path],
    table_id: str,
    write_disposition: str = "WRITE_APPEND",
) -> int:
    _require_gcp()
    from google.cloud import bigquery

    client = bigquery.Client(project=settings.gcp_project)
    table_ref = _table_ref(table_id)
    loaded = 0

    if write_disposition == "WRITE_TRUNCATE":
        client.delete_table(table_ref, not_found_ok=True)

    for path in local_paths:
        if not path.is_file():
            logger.warning("bq_local_skip", path=str(path), reason="missing")
            continue
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            autodetect=True,
            schema_update_options=[
                bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION,
            ],
        )
        with path.open("rb") as handle:
            job = client.load_table_from_file(handle, table_ref, job_config=job_config)
        job.result()
        loaded += 1
        logger.info("bq_loaded_local", table=table_ref, path=str(path))

    return loaded


def upload_parquet_file(local_path: Path, gcs_blob: str) -> str:
    _require_gcs()
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


def _layer_local_parquets(layer: str) -> list[Path]:
    layer_paths = {
        "bronze": settings.bronze_path,
        "silver": settings.silver_path,
        "gold": settings.gold_path,
    }
    if layer == "silver_sofascore":
        path = settings.sofascore_stats_dir / MATCH_STATS_PARQUET
        return [path] if path.is_file() else []

    if layer == "silver_sofascore_enrich":
        path = settings.sofascore_enrich_dir / MATCH_ENRICH_PARQUET
        return [path] if path.is_file() else []

    local_dir = layer_paths.get(layer)
    if local_dir is None:
        return []
    if not local_dir.exists():
        return []
    return sorted(local_dir.rglob("*.parquet"))


def _sync_dataframe_layer(
    df,
    layer: str,
    table: str,
    *,
    gcs_filename: str = "snapshot.parquet",
    write_disposition: str = "WRITE_APPEND",
) -> dict:
    rows = len(df) if df is not None and not df.empty else 0
    if settings.gcs_bucket:
        files, uri = load_dataframe_via_gcs(
            df,
            layer,
            table,
            filename=gcs_filename,
            write_disposition=write_disposition,
        )
        return {
            "layer": layer,
            "files": files,
            "table": table,
            "mode": "gcs",
            "rows": rows,
            "gcs_uri": uri or None,
        }
    files = load_dataframe_to_bigquery(df, table, write_disposition=write_disposition)
    return {
        "layer": layer,
        "files": files,
        "table": table,
        "mode": "dataframe",
        "rows": rows,
    }


def sync_layer(layer: str, write_disposition: str = "WRITE_APPEND") -> dict:
    layer = resolve_layer(layer)
    table = MEDALLION_TABLES[layer]

    if layer == "bronze_sofascore":
        return _sync_dataframe_layer(
            load_bronze_sofascore_events(),
            layer,
            table,
            gcs_filename="events.parquet",
            write_disposition=write_disposition,
        )

    if layer == "bronze_superbet":
        from ingest.superbet.dataset import load_bronze_superbet_events

        return _sync_dataframe_layer(
            load_bronze_superbet_events(),
            layer,
            table,
            gcs_filename="snapshots.parquet",
            write_disposition=write_disposition,
        )

    if layer == "silver_fixtures":
        import pandas as pd

        from ingest.fixtures.world_cup import load_wc_fixtures

        df = load_wc_fixtures()
        if not df.empty:
            if "group_name" in df.columns:
                df["group_name"] = df["group_name"].astype("string")
            if "match_date" in df.columns:
                df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
        return _sync_dataframe_layer(
            df,
            layer,
            table,
            gcs_filename="world_cup_fixtures.parquet",
            write_disposition=write_disposition,
        )

    if layer == "gold_wc":
        return _sync_dataframe_layer(
            build_gold_wc_match_features_df(),
            layer,
            table,
            gcs_filename="match_features.parquet",
            write_disposition=write_disposition,
        )

    if layer in ("bronze", "silver", "gold"):
        return _sync_dataframe_layer(
            load_layer_dataframe(layer),
            layer,
            table,
            gcs_filename="articles.parquet",
            write_disposition=write_disposition,
        )

    local_paths = _layer_local_parquets(layer)

    if settings.gcs_bucket:
        if layer == "silver_sofascore":
            import pandas as pd

            parquet_path = settings.sofascore_stats_dir / MATCH_STATS_PARQUET
            if parquet_path.is_file():
                df = prepare_dataframe_for_bq(pd.read_parquet(parquet_path))
                files, uri = load_dataframe_via_gcs(
                    df,
                    layer,
                    table,
                    filename=MATCH_STATS_PARQUET,
                    write_disposition=write_disposition,
                )
                return {
                    "layer": layer,
                    "files": files,
                    "table": table,
                    "mode": "gcs",
                    "gcs_uri": uri or None,
                    "rows": len(df),
                }
            return {"layer": layer, "files": 0, "table": table, "mode": "gcs"}

    files = load_local_parquet_to_bigquery(
        local_paths,
        table,
        write_disposition=write_disposition,
    )
    return {
        "layer": layer,
        "files": files,
        "table": table,
        "mode": "local",
    }


def sync_all_layers(write_disposition: str = "WRITE_APPEND") -> list[dict]:
    return [
        sync_layer(layer, write_disposition=write_disposition)
        for layer in SYNC_LAYER_ORDER
    ]
