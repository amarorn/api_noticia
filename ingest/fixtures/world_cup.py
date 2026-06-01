from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
import structlog

from config import settings
from ingest.fixtures.wc_parser import parse_world_cup_txt
from schemas.models import MatchResult

logger = structlog.get_logger()

OPENFOOTBALL_WC_BASE = "https://raw.githubusercontent.com/openfootball/worldcup/master"

WC_EDITIONS: dict[int, str] = {
    1986: "1986--mexico",
    1990: "1990--italy",
    1994: "1994--usa",
    1998: "1998--france",
    2002: "2002--south-korea-n-japan",
    2006: "2006--germany",
    2010: "2010--south-africa",
    2014: "2014--brazil",
    2018: "2018--russia",
    2022: "2022--qatar",
}

DEFAULT_WC_SEASONS = list(WC_EDITIONS.keys())


async def _fetch_text(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def fetch_edition(season: int) -> list[MatchResult]:
    folder = WC_EDITIONS.get(season)
    if not folder:
        raise ValueError(f"Edição {season} não mapeada. Disponíveis: {list(WC_EDITIONS)}")

    matches: list[MatchResult] = []
    for filename, phase in [("cup.txt", "group"), ("cup_finals.txt", "knockout")]:
        url = f"{OPENFOOTBALL_WC_BASE}/{folder}/{filename}"
        try:
            content = await _fetch_text(url)
            parsed = parse_world_cup_txt(content, season=season, default_phase=phase)
            matches.extend(parsed)
            logger.info("wc_file_fetched", season=season, file=filename, matches=len(parsed))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("wc_file_missing", season=season, file=filename)
            else:
                raise

    logger.info("wc_edition_fetched", season=season, total_matches=len(matches))
    return matches


def save_wc_fixtures(matches: list[MatchResult]) -> Path | None:
    if not matches:
        return None

    settings.fixtures_path.mkdir(parents=True, exist_ok=True)
    records = [m.model_dump(mode="json") for m in matches]
    df = pd.DataFrame(records)

    season = matches[0].season
    out_path = settings.fixtures_path / f"world_cup_{season}.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("wc_fixtures_saved", path=str(out_path), rows=len(df))
    return out_path


def load_wc_fixtures(seasons: list[int] | None = None) -> pd.DataFrame:
    root = settings.fixtures_path
    if not root.exists():
        return pd.DataFrame()

    if seasons:
        frames = []
        for season in seasons:
            path = root / f"world_cup_{season}.parquet"
            if path.exists():
                frames.append(pd.read_parquet(path))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    files = sorted(root.glob("world_cup_*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


async def import_wc_seasons(seasons: list[int] | None = None) -> pd.DataFrame:
    target = seasons or DEFAULT_WC_SEASONS
    all_matches: list[MatchResult] = []

    for season in target:
        try:
            matches = await fetch_edition(season)
            save_wc_fixtures(matches)
            all_matches.extend(matches)
        except Exception as exc:
            logger.error("wc_import_failed", season=season, error=str(exc))

    if not all_matches:
        return pd.DataFrame()

    return pd.DataFrame([m.model_dump(mode="json") for m in all_matches])
