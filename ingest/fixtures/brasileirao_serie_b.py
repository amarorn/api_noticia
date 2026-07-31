"""Import Brasileirão Série B (openfootball ``{season}_br2.txt``)."""
from __future__ import annotations

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
COMPETITION_LABEL = "Brasileirão Série B"


async def fetch_season(season: int) -> list[MatchResult]:
    url = f"{OPENFOOTBALL_BASE}/{season}_br2.txt"
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code == 404:
            logger.warning("serie_b_season_not_found", season=season, url=url)
            return []
        response.raise_for_status()
        matches = parse_football_txt(response.text, season=season, competition=COMPETITION_LABEL)
        logger.info("serie_b_fetched", season=season, matches=len(matches), url=url)
        return matches


def save_fixtures(matches: list[MatchResult]) -> Path | None:
    if not matches:
        return None
    from ingest.fixtures.store import save_fixtures_df

    df = pd.DataFrame([m.model_dump(mode="json") for m in matches])
    season = matches[0].season
    out_path = save_fixtures_df(df, competition="brasileirao_serie_b", season=season)
    if out_path:
        logger.info("serie_b_saved", path=str(out_path), rows=len(df))
    return out_path


async def import_seasons(seasons: list[int]) -> pd.DataFrame:
    all_matches: list[MatchResult] = []
    for season in seasons:
        try:
            matches = await fetch_season(season)
            save_fixtures(matches)
            all_matches.extend(matches)
        except Exception as exc:
            logger.error("serie_b_import_failed", season=season, error=str(exc))
    if not all_matches:
        return pd.DataFrame()
    return pd.DataFrame([m.model_dump(mode="json") for m in all_matches])
