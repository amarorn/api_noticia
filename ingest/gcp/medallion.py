from __future__ import annotations

MEDALLION_TABLES: dict[str, str] = {
    "bronze": "bronze_articles",
    "bronze_sofascore": "bronze_sofascore_events",
    "silver": "silver_articles",
    "silver_sofascore": "silver_sofascore_match_stats",
    "silver_fixtures": "silver_fixtures_results",
    "gold": "gold_bolao_context",
    "gold_wc": "gold_wc_match_features",
}

LAYER_ALIASES: dict[str, str] = {
    "sofascore": "silver_sofascore",
    "fixtures": "silver_fixtures",
}

SYNC_LAYER_ORDER: list[str] = [
    "bronze",
    "bronze_sofascore",
    "silver",
    "silver_sofascore",
    "silver_fixtures",
    "gold",
    "gold_wc",
]

LEGACY_BQ_TABLES: dict[str, str] = {
    "sofascore_match_stats": "silver_sofascore_match_stats",
    "fixtures_results": "silver_fixtures_results",
}

# Layout no GCS (medalhão): gs://{bucket}/{prefix}/...
GCS_LAYER_PREFIX: dict[str, str] = {
    "bronze": "lake/bronze/articles",
    "bronze_sofascore": "lake/bronze/sofascore",
    "silver": "lake/silver/articles",
    "silver_sofascore": "lake/silver/sofascore",
    "silver_fixtures": "lake/silver/fixtures",
    "gold": "lake/gold/bolao",
    "gold_wc": "lake/gold/wc",
}

DEFAULT_GCS_BUCKET = "beanalytic-dev-sports-news-lake"


def resolve_layer(layer: str) -> str:
    return LAYER_ALIASES.get(layer, layer)


def gcs_snapshot_blob(layer: str, filename: str = "snapshot.parquet") -> str:
    prefix = GCS_LAYER_PREFIX.get(layer, f"lake/{layer}")
    return f"{prefix}/{filename}"
