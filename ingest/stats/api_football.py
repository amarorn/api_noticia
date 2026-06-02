from __future__ import annotations

from datetime import datetime

import httpx
import structlog

from config import settings

logger = structlog.get_logger()


class ApiFootballClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        key = api_key or settings.api_football_key
        if not key:
            raise ValueError("Defina API_FOOTBALL_KEY no .env")
        self._base = (base_url or settings.api_football_base_url).rstrip("/")
        self._headers = {"x-apisports-key": key}

    async def get_fixture_statistics(
        self,
        fixture_id: int,
    ) -> dict | None:
        url = f"{self._base}/fixtures/statistics"
        params = {"fixture": fixture_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers, params=params)
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("response") or []
            return rows if rows else None

    async def find_fixture_id(
        self,
        home_team: str,
        away_team: str,
        match_date: datetime,
        league_id: int = 71,
        season: int | None = None,
    ) -> int | None:
        url = f"{self._base}/fixtures"
        params: dict = {
            "league": league_id,
            "season": season or match_date.year,
            "date": match_date.strftime("%Y-%m-%d"),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers, params=params)
            response.raise_for_status()
            for item in response.json().get("response") or []:
                teams = item.get("teams") or {}
                home = (teams.get("home") or {}).get("name", "")
                away = (teams.get("away") or {}).get("name", "")
                if home_team.lower() in home.lower() and away_team.lower() in away.lower():
                    return item.get("fixture", {}).get("id")
        return None


def summarize_fixture_stats(stats_rows: list[dict]) -> dict:
    """Extrai métricas agregadas para enriquecer BolaoFeature."""
    out: dict = {}
    for block in stats_rows:
        team_side = "home" if stats_rows.index(block) == 0 else "away"
        prefix = team_side
        for stat in block.get("statistics") or []:
            stat_type = (stat.get("type") or "").lower()
            value = stat.get("value")
            if stat_type == "shots on goal":
                out[f"{prefix}_shots_on_target"] = _to_int(value)
            elif stat_type == "ball possession":
                out[f"{prefix}_possession_pct"] = _to_int(str(value).replace("%", ""))
    return out


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
