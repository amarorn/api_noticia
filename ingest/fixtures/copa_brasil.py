from pathlib import Path

import httpx
import pandas as pd
import structlog

from ingest.fixtures.parser import parse_football_txt
from ingest.fixtures.store import save_fixtures_df
from schemas.models import MatchResult

logger = structlog.get_logger()

OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/openfootball/south-america/master/brazil"
)


async def fetch_season(season: int) -> list[MatchResult]:
    url = f"{OPENFOOTBALL_BASE}/{season}_brcup.txt"
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code == 404:
            logger.warning("copa_season_not_found", season=season, url=url)
            return []
        response.raise_for_status()
        matches = parse_football_txt(
            response.text, season=season, competition="Copa do Brasil"
        )
        logger.info("copa_season_fetched", season=season, matches=len(matches), url=url)
        return matches


def save_fixtures(matches: list[MatchResult]) -> Path | None:
    if not matches:
        return None
    season = matches[0].season
    df = pd.DataFrame([m.model_dump(mode="json") for m in matches])
    path = save_fixtures_df(df, competition="copa_brasil", season=season)
    if path:
        logger.info("copa_fixtures_saved", path=str(path), rows=len(df))
    return path


async def import_seasons(seasons: list[int]) -> pd.DataFrame:
    all_matches: list[MatchResult] = []
    for season in seasons:
        try:
            matches = await fetch_season(season)
            save_fixtures(matches)
            all_matches.extend(matches)
        except Exception as exc:
            logger.error("copa_season_import_failed", season=season, error=str(exc))

    if not all_matches:
        return pd.DataFrame()
    return pd.DataFrame([m.model_dump(mode="json") for m in all_matches])
