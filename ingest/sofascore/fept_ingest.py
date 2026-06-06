from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from config import settings
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.event_helpers import find_event_id
from ingest.sofascore.kxl_sofascore_ingest import build_kxl_sofascore_payload
from ingest.sofascore.teams import (
    load_team_map,
    sofascore_search_query,
)
from schemas.national_teams import normalize_national_team
from schemas.wc_kxl_dynamic import FeptEscalacao, WcKxlMatchInput, WcKxlPartida

logger = structlog.get_logger()


@dataclass(frozen=True)
class FeptIngestResult:
    home_team: str
    away_team: str
    event_id: int
    match_date: str | None
    fept: FeptEscalacao
    ratings_found: int
    ratings_missing: int
    source: str = "sofascore"

    def to_payload(self) -> dict[str, Any]:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "event_id": self.event_id,
            "match_date": self.match_date,
            "source": self.source,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "meta": {
                "ratings_found": self.ratings_found,
                "ratings_missing": self.ratings_missing,
            },
            "kxl_match": WcKxlMatchInput(
                partida=WcKxlPartida(
                    mandante=self.home_team,
                    visitante=self.away_team,
                ),
                fept=self.fept,
            ).model_dump(exclude_none=True),
        }


def build_fept_payload(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
) -> FeptIngestResult:
    return build_kxl_sofascore_payload(
        home_team=home_team,
        away_team=away_team,
        event_id=event_id,
        match_date=match_date,
        client=client,
        team_map=team_map,
    ).to_fept_result()


def save_fept_payload(payload: dict[str, Any], *, output_dir: Path | None = None) -> Path:
    root = output_dir or settings.sofascore_fept_dir
    root.mkdir(parents=True, exist_ok=True)
    event_id = payload.get("event_id", "unknown")
    home = str(payload.get("home_team", "home")).replace(" ", "-")
    away = str(payload.get("away_team", "away")).replace(" ", "-")
    path = root / f"{event_id}_{home}_x_{away}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ingest_fept(
    *,
    home_team: str | None,
    away_team: str | None,
    event_id: int | None = None,
    match_date: date | None = None,
    save: bool = True,
    output_dir: Path | None = None,
) -> tuple[FeptIngestResult, Path | None]:
    kxl_result = build_kxl_sofascore_payload(
        home_team=home_team,
        away_team=away_team,
        event_id=event_id,
        match_date=match_date,
    )
    path = (
        save_fept_payload(kxl_result.to_payload(), output_dir=output_dir) if save else None
    )
    return kxl_result.to_fept_result(), path


def build_team_map_from_squads(
    *,
    squads_path: Path | None = None,
    client: SofascoreClient | None = None,
) -> dict[str, dict]:
    squads_file = squads_path or settings.wc_squads_path
    data = json.loads(squads_file.read_text(encoding="utf-8"))
    sofascore = client or SofascoreClient()
    teams: dict[str, dict] = {}
    for squad in data.get("squads") or []:
        canonical = normalize_national_team(str(squad.get("team") or ""))
        if not canonical:
            continue
        query = sofascore_search_query(canonical)
        entity = sofascore.search_team(query)
        if not entity:
            logger.warning("sofascore_team_missing", team=canonical, query=query)
            continue
        teams[canonical] = {
            "sofascore_id": int(entity["id"]),
            "sofascore_name": entity.get("name"),
            "slug": entity.get("slug"),
            "search_query": query,
        }
    return teams
