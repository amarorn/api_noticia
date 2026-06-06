from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from config import settings
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.enrich_mapper import flatten_enrich_features
from ingest.sofascore.event_helpers import find_event_id, resolve_match_date
from ingest.sofascore.teams import load_team_map
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()

ENRICH_PARQUET = "match_enrich.parquet"


@dataclass(frozen=True)
class EnrichIngestResult:
    event_id: int
    home_team: str
    away_team: str
    match_date: str | None
    features: dict[str, Any]
    json_path: Path | None
    parquet_path: Path | None

    def to_payload(self) -> dict[str, Any]:
        return {
            **self.features,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


def build_enrich_payload(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
) -> EnrichIngestResult:
    """Busca dados enriquecidos (pregame-form, team-streaks, h2h, incidents) do Sofascore."""
    team_map = team_map if team_map is not None else load_team_map()
    sofascore = client or SofascoreClient()

    if event_id is not None:
        event = sofascore.event(event_id)
        home = normalize_national_team(home_team) if home_team else None
        away = normalize_national_team(away_team) if away_team else None
        if not home or not away:
            from ingest.sofascore.event_helpers import canonical_from_event_team

            home = canonical_from_event_team(event.get("homeTeam") or {}, team_map)
            away = canonical_from_event_team(event.get("awayTeam") or {}, team_map)
        resolved_date = resolve_match_date(event, match_date)
    else:
        if match_date is None or not home_team or not away_team:
            raise ValueError("Informe event_id ou home_team + away_team + match_date")
        home = normalize_national_team(home_team)
        away = normalize_national_team(away_team)
        event = find_event_id(
            sofascore,
            home_team=home,
            away_team=away,
            match_date=match_date,
            team_map=team_map,
        )
        event_id = int(event["id"])
        resolved_date = resolve_match_date(event, match_date)

    # Busca todos os endpoints enriquecidos
    pregame_form = None
    team_streaks = None
    h2h = None
    incidents = None

    try:
        pregame_form = sofascore.event_pregame_form(event_id)
    except Exception as exc:
        logger.warning("enrich_pregame_form_failed", event_id=event_id, error=str(exc))

    try:
        team_streaks = sofascore.event_team_streaks(event_id)
    except Exception as exc:
        logger.warning("enrich_team_streaks_failed", event_id=event_id, error=str(exc))

    try:
        h2h = sofascore.event_h2h(event_id)
    except Exception as exc:
        logger.warning("enrich_h2h_failed", event_id=event_id, error=str(exc))

    try:
        incidents = sofascore.event_incidents(event_id)
    except Exception as exc:
        logger.warning("enrich_incidents_failed", event_id=event_id, error=str(exc))

    features = flatten_enrich_features(
        event_id=event_id,
        home_team=home,
        away_team=away,
        match_date=resolved_date,
        pregame_form=pregame_form,
        team_streaks=team_streaks,
        h2h=h2h,
        incidents=incidents,
    )

    logger.info(
        "sofascore_enrich_ingested",
        event_id=event_id,
        home=home,
        away=away,
        features=len(features),
    )

    return EnrichIngestResult(
        event_id=event_id,
        home_team=home,
        away_team=away,
        match_date=resolved_date,
        features=features,
        json_path=None,
        parquet_path=None,
    )


def save_enrich_json(payload: dict[str, Any], *, output_dir: Path | None = None) -> Path | None:
    from ingest.gcp.lake_store import cloud_lake_enabled

    if cloud_lake_enabled():
        return None

    root = output_dir or settings.sofascore_enrich_dir
    root.mkdir(parents=True, exist_ok=True)
    event_id = payload.get("event_id", "unknown")
    home = str(payload.get("home_team", "home")).replace(" ", "-")
    away = str(payload.get("away_team", "away")).replace(" ", "-")
    path = root / f"{event_id}_{home}_x_{away}_enrich.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def upsert_enrich_parquet(
    row: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> Path:
    from ingest.sofascore.enrich_dataset import upsert_enrich_row

    upsert_enrich_row(row, enrich_dir=output_dir)
    root = output_dir or settings.sofascore_enrich_dir
    return root / ENRICH_PARQUET


def ingest_enrich(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
    save: bool = True,
    output_dir: Path | None = None,
) -> EnrichIngestResult:
    """Busca e persiste dados enriquecidos de um confronto."""
    result = build_enrich_payload(
        home_team=home_team,
        away_team=away_team,
        event_id=event_id,
        match_date=match_date,
        client=client,
        team_map=team_map,
    )
    payload = result.to_payload()
    json_path = None
    parquet_path = None
    if save:
        json_path = save_enrich_json(payload, output_dir=output_dir)
        parquet_path = upsert_enrich_parquet(payload, output_dir=output_dir)
    return EnrichIngestResult(
        event_id=result.event_id,
        home_team=result.home_team,
        away_team=result.away_team,
        match_date=result.match_date,
        features=result.features,
        json_path=json_path,
        parquet_path=parquet_path,
    )


def load_enrich_features(event_id: int, *, output_dir: Path | None = None) -> dict[str, Any] | None:
    from ingest.sofascore.enrich_dataset import load_raw_enrich_df

    df = load_raw_enrich_df(enrich_dir=output_dir)
    if df.empty:
        return None
    rows = df[df["event_id"] == event_id]
    if rows.empty:
        return None
    return rows.iloc[-1].to_dict()
