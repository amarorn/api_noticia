import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import structlog

from config import settings
from ingest.storage import load_bronze
from schemas.models import SilverArticle
from pipelines.national_team_entities import extract_national_teams
from schemas.teams import BRAZILIAN_TEAMS

logger = structlog.get_logger()

INJURY_KEYWORDS = [
    "lesão", "lesionado", "contundido", "machucado", "desfalque", "fora",
    "cirurgia", "recuperação", "dm", "departamento médico", "indisponível",
]

POSITIVE_KEYWORDS = ["vitória", "gol", "artilheiro", "confiante", "invicto", "classificação"]
NEGATIVE_KEYWORDS = ["derrota", "rebaixamento", "crise", "demissão", "suspenso", "eliminação"]


def _extract_entities(text: str) -> tuple[list[str], list[str]]:
    text_lower = text.lower()
    teams = [t for t in BRAZILIAN_TEAMS if t.lower() in text_lower]
    players: list[str] = []
    return teams, players


def _optional_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text if text else None


def _optional_datetime(value: object) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        dt = pd.to_datetime(value, utc=True)
        if pd.isna(dt):
            return None
        return dt.to_pydatetime()
    except (TypeError, ValueError):
        return None


def _required_datetime(value: object) -> datetime:
    parsed = _optional_datetime(value)
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def _simple_sentiment(text: str) -> float:
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def bronze_to_silver(df: pd.DataFrame) -> list[SilverArticle]:
    articles: list[SilverArticle] = []
    for _, row in df.iterrows():
        body = (
            _optional_str(row.get("content_raw"))
            or _optional_str(row.get("summary"))
            or _optional_str(row.get("title"))
            or ""
        )
        title = _optional_str(row.get("title")) or ""
        full_text = f"{title} {body}"
        teams, players = _extract_entities(full_text)
        national_teams = extract_national_teams(full_text)

        article = SilverArticle(
            id=str(row["id"]),
            source=str(row["source"]),
            source_url=row["source_url"],
            title=title,
            body=body,
            summary=_optional_str(row.get("summary")),
            published_at=_optional_datetime(row.get("published_at")),
            scraped_at=_required_datetime(row.get("scraped_at")),
            content_hash=str(row["content_hash"]),
            teams_mentioned=teams,
            national_teams_mentioned=national_teams,
            players_mentioned=players,
            categories=row.get("raw_payload", {}).get("tags", []) if isinstance(row.get("raw_payload"), dict) else [],
            sentiment_score=_simple_sentiment(full_text),
        )
        articles.append(article)
    return articles


def save_silver(articles: list[SilverArticle]) -> Path | None:
    if not articles:
        return None

    from ingest.gcp.lake_store import cloud_lake_enabled, write_layer_snapshot
    from ingest.gcp.lake_frames import normalize_silver_df

    records = [a.model_dump(mode="json") for a in articles]
    df = pd.DataFrame(records)

    if cloud_lake_enabled():
        existing = load_silver()
        combined = pd.concat([existing, df], ignore_index=True)
        dedup_col = "content_hash" if "content_hash" in combined.columns else "id"
        combined = combined.drop_duplicates(subset=[dedup_col], keep="last")
        write_layer_snapshot("silver", normalize_silver_df(combined))
        logger.info("silver_saved_cloud", rows=len(combined), batch=len(df))
        return settings.silver_path / "cloud_snapshot.parquet"

    settings.silver_path.mkdir(parents=True, exist_ok=True)
    dt = datetime.now(timezone.utc)
    out_path = (
        settings.silver_path
        / f"year={dt.year}"
        / f"month={dt.month:02d}"
        / f"day={dt.day:02d}"
        / f"articles_{dt.strftime('%H%M%S')}.parquet"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    logger.info("silver_saved", path=str(out_path), rows=len(df))
    return out_path


def _silver_article_parquet_files(root: Path) -> list[Path]:
    """Lista parquets de artigos RSS (exclui silver/inplay e outros auxiliares)."""
    return sorted(
        f
        for f in root.glob("**/articles_*.parquet")
        if "inplay" not in f.relative_to(root).parts
    )


def silver_fingerprint() -> str:
    from ingest.gcp.lake_store import cloud_lake_enabled, layer_fingerprint

    if cloud_lake_enabled():
        return layer_fingerprint("silver")

    root = settings.silver_path
    if not root.exists():
        return "empty"
    files = _silver_article_parquet_files(root)
    if not files:
        return "empty"
    parts = [f"{f.relative_to(root)}:{f.stat().st_mtime_ns}:{f.stat().st_size}" for f in files]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def load_silver() -> pd.DataFrame:
    from ingest.gcp.lake_store import cloud_lake_enabled, read_layer_snapshot
    from ingest.gcp.lake_frames import normalize_silver_df

    if cloud_lake_enabled():
        return normalize_silver_df(read_layer_snapshot("silver"))

    silver_root = settings.silver_path
    if not silver_root.exists():
        return pd.DataFrame()
    files = _silver_article_parquet_files(silver_root)
    if not files:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for path in files:
        try:
            frames.append(pd.read_parquet(path))
        except Exception as exc:
            logger.warning("silver_parquet_read_failed", path=str(path), error=str(exc))

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    dedup_col = "content_hash" if "content_hash" in df.columns else "id"
    return df.drop_duplicates(subset=[dedup_col], keep="last")


def run_silver_pipeline() -> Path | None:
    bronze_df = load_bronze()
    if bronze_df.empty:
        logger.warning("no_bronze_data")
        return None
    articles = bronze_to_silver(bronze_df)
    return save_silver(articles)
