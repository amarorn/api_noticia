import time

from ingest.fixtures.brasileirao import load_fixtures
from pipelines.silver import load_silver

_CACHE_TTL_SECONDS = 30.0
_counts_cache: dict[str, float | int] = {"articles_silver": 0, "fixtures": 0, "at": 0.0}


def get_lake_counts(*, force: bool = False) -> tuple[int, int]:
    now = time.monotonic()
    if (
        not force
        and now - float(_counts_cache["at"]) < _CACHE_TTL_SECONDS
    ):
        return int(_counts_cache["articles_silver"]), int(_counts_cache["fixtures"])

    silver_df = load_silver()
    fixtures_df = load_fixtures()
    _counts_cache["articles_silver"] = len(silver_df)
    _counts_cache["fixtures"] = len(fixtures_df)
    _counts_cache["at"] = now
    return int(_counts_cache["articles_silver"]), int(_counts_cache["fixtures"])


def invalidate_lake_counts() -> None:
    _counts_cache["at"] = 0.0
