from pathlib import Path

import httpx
import pandas as pd
import structlog

from ingest.fixtures.parser import parse_football_txt
from schemas.models import MatchResult

logger = structlog.get_logger()

OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/openfootball/south-america/master/brazil"
)


async def fetch_season(season: int) -> list[MatchResult]:
    url = f"{OPENFOOTBALL_BASE}/{season}_br1.txt"
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        matches = parse_football_txt(response.text, season=season)
        logger.info("season_fetched", season=season, matches=len(matches), url=url)
        return matches


def save_fixtures(matches: list[MatchResult]) -> Path | None:
    if not matches:
        return None

    from ingest.fixtures.store import save_fixtures_df

    records = [m.model_dump(mode="json") for m in matches]
    df = pd.DataFrame(records)
    season = matches[0].season
    out_path = save_fixtures_df(df, competition="brasileirao", season=season)
    if out_path:
        logger.info("fixtures_saved", path=str(out_path), rows=len(df))
    return out_path


def load_fixtures(season: int | None = None) -> pd.DataFrame:
    from ingest.fixtures.store import load_fixtures as load_all

    return load_all(season=season, competition="brasileirao")


async def import_seasons(seasons: list[int]) -> pd.DataFrame:
    all_matches: list[MatchResult] = []
    for season in seasons:
        try:
            matches = await fetch_season(season)
            save_fixtures(matches)
            all_matches.extend(matches)
        except Exception as exc:
            logger.error("season_import_failed", season=season, error=str(exc))

    if not all_matches:
        return pd.DataFrame()

    return pd.DataFrame([m.model_dump(mode="json") for m in all_matches])
