"""Remove partições de notícias (bronze/silver) para recarga limpa."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from config import settings

logger = structlog.get_logger()


def _partition_date(path: Path) -> datetime | None:
    parts = path.parts
    year = month = day = None
    for part in parts:
        if part.startswith("year="):
            year = int(part.split("=", 1)[1])
        elif part.startswith("month="):
            month = int(part.split("=", 1)[1])
        elif part.startswith("day="):
            day = int(part.split("=", 1)[1])
    if year is None or month is None or day is None:
        return None
    return datetime(year, month, day, tzinfo=timezone.utc)


def _should_remove(path: Path, *, cutoff: datetime | None) -> bool:
    if cutoff is None:
        return True
    part_date = _partition_date(path)
    if part_date is None:
        return True
    return part_date >= cutoff


def _prune_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def purge_news(*, days: int | None = None, clear_meta: bool = True) -> dict:
    cutoff = None
    if days is not None and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    removed_bronze = 0
    removed_silver = 0

    for layer, counter_name in (
        (settings.bronze_path, "removed_bronze"),
        (settings.silver_path, "removed_silver"),
    ):
        if not layer.exists():
            continue
        for parquet in list(layer.rglob("*.parquet")):
            if not _should_remove(parquet, cutoff=cutoff):
                continue
            parquet.unlink()
            if counter_name == "removed_bronze":
                removed_bronze += 1
            else:
                removed_silver += 1
        _prune_empty_dirs(layer)

    meta_cleared = False
    if clear_meta:
        meta_file = settings.lake_root / "_meta" / "collections.jsonl"
        if meta_file.exists():
            meta_file.write_text("", encoding="utf-8")
            meta_cleared = True

    result = {
        "removed_bronze": removed_bronze,
        "removed_silver": removed_silver,
        "days": days,
        "meta_cleared": meta_cleared,
    }
    logger.info("news_purged", **result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apaga parquets de notícias (bronze/silver). Use com daily-sync em seguida.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Só partições dos últimos N dias (omitir = apaga todo bronze/silver de notícias)",
    )
    parser.add_argument(
        "--keep-meta",
        action="store_true",
        help="Não limpar data/lake/_meta/collections.jsonl",
    )
    args = parser.parse_args()

    result = purge_news(days=args.days, clear_meta=not args.keep_meta)
    print(
        f"Removidos: {result['removed_bronze']} bronze, "
        f"{result['removed_silver']} silver"
        + (f" (últimos {args.days} dias)" if args.days else " (lake de notícias inteiro)")
    )
    if result["meta_cleared"]:
        print("Log de coletas (_meta/collections.jsonl) zerado.")
    print("Próximo passo: daily-sync  ou  POST /news/sync")


if __name__ == "__main__":
    main()
