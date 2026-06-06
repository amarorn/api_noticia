from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from config import settings
from ingest.sofascore.paths import MATCH_STATS_PARQUET


def _require_duckdb():
    try:
        import duckdb
    except ImportError as exc:
        raise ImportError(
            'DuckDB não instalado. Execute: pip install -e ".[analytics]"'
        ) from exc
    return duckdb


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def lake_parquet_sources() -> dict[str, str]:
    """Globs Parquet por camada do lake (para SQL DuckDB)."""
    sofascore = _sql_path(settings.sofascore_stats_dir / MATCH_STATS_PARQUET)
    fixtures = _sql_path(settings.fixtures_path / "**" / "*.parquet")
    return {
        "bronze": _sql_path(settings.bronze_path / "**" / "*.parquet"),
        "silver": _sql_path(settings.silver_path / "**" / "*.parquet"),
        "gold": _sql_path(settings.gold_path / "**" / "*.parquet"),
        "fixtures": fixtures,
        "silver_fixtures": fixtures,
        "sofascore": sofascore,
        "silver_sofascore": sofascore,
    }


def _glob_exists(glob_path: str) -> bool:
    root = glob_path.split("*", 1)[0]
    if "*" not in glob_path:
        return Path(glob_path).is_file()
    base = Path(root)
    if not base.exists():
        return False
    pattern = glob_path[len(root) :]
    return any(base.rglob(pattern.lstrip("/")))


def register_lake_views(conn) -> dict[str, bool]:
    """Registra views medalhão (bronze/silver/gold + domínios WC/Sofascore)."""
    sources = lake_parquet_sources()
    available: dict[str, bool] = {}
    for layer, glob_path in sources.items():
        exists = _glob_exists(glob_path)
        available[layer] = exists
        if exists:
            conn.execute(
                f"CREATE OR REPLACE VIEW {layer} AS "
                f"SELECT * FROM read_parquet('{glob_path}')"
            )
        else:
            conn.execute(f"CREATE OR REPLACE VIEW {layer} AS SELECT 1 WHERE false")
    return available


def query_lake(sql: str) -> pd.DataFrame:
    duckdb = _require_duckdb()
    conn = duckdb.connect()
    try:
        register_lake_views(conn)
        return conn.execute(sql).fetchdf()
    finally:
        conn.close()


def lake_summary() -> dict[str, Any]:
    """Contagens rápidas por camada."""
    duckdb = _require_duckdb()
    conn = duckdb.connect()
    try:
        available = register_lake_views(conn)
        summary: dict[str, Any] = {"layers": {}}
        for layer, ok in available.items():
            if not ok:
                summary["layers"][layer] = {"available": False, "rows": 0}
                continue
            rows = int(conn.execute(f"SELECT COUNT(*) FROM {layer}").fetchone()[0])
            summary["layers"][layer] = {"available": True, "rows": rows}
        return summary
    finally:
        conn.close()


def team_sofascore_summary(team: str, *, limit: int = 5) -> pd.DataFrame:
    from schemas.national_teams import normalize_national_team

    canonical = normalize_national_team(team).replace("'", "''")
    sql = f"""
        SELECT
            match_date,
            home_team,
            away_team,
            home_xg,
            away_xg,
            home_corners,
            away_corners
        FROM sofascore
        WHERE home_team = '{canonical}' OR away_team = '{canonical}'
        ORDER BY match_date DESC
        LIMIT {int(limit)}
    """
    return query_lake(sql)
