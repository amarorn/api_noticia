from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from config import settings
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.paths import MATCH_STATS_PARQUET
from ingest.sofascore.event_helpers import resolve_match_date
from ingest.sofascore.event_helpers import find_event_id
from ingest.sofascore.stats_mapper import flatten_match_stats
from ingest.sofascore.teams import load_team_map
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


@dataclass(frozen=True)
class MatchStatsIngestResult:
    event_id: int
    home_team: str
    away_team: str
    match_date: str | None
    stats: dict[str, Any]
    json_path: Path | None
    parquet_path: Path | None

    def to_payload(self) -> dict[str, Any]:
        return {
            **self.stats,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


def build_match_stats_payload(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
    include_incidents: bool = True,
) -> MatchStatsIngestResult:
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

    statistics_payload = sofascore.event_statistics(event_id)
    incidents_payload = (
        sofascore.event_incidents(event_id) if include_incidents else None
    )
    stats = flatten_match_stats(
        event_id=event_id,
        home_team=home,
        away_team=away,
        match_date=resolved_date,
        statistics_payload=statistics_payload,
        incidents_payload=incidents_payload,
    )

    logger.info(
        "sofascore_stats_ingested",
        event_id=event_id,
        home=home,
        away=away,
        metrics=len([k for k in stats if k.startswith(("home_", "away_"))]),
    )
    return MatchStatsIngestResult(
        event_id=event_id,
        home_team=home,
        away_team=away,
        match_date=resolved_date,
        stats=stats,
        json_path=None,
        parquet_path=None,
    )


def save_match_stats_json(payload: dict[str, Any], *, output_dir: Path | None = None) -> Path | None:
    from ingest.gcp.lake_store import cloud_lake_enabled

    if cloud_lake_enabled():
        return None

    root = output_dir or settings.sofascore_stats_dir
    root.mkdir(parents=True, exist_ok=True)
    event_id = payload.get("event_id", "unknown")
    home = str(payload.get("home_team", "home")).replace(" ", "-")
    away = str(payload.get("away_team", "away")).replace(" ", "-")
    path = root / f"{event_id}_{home}_x_{away}_stats.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def upsert_match_stats_parquet(
    row: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> Path:
    from ingest.sofascore.stats_dataset import upsert_match_stats_row

    upsert_match_stats_row(row, stats_dir=output_dir)
    root = output_dir or settings.sofascore_stats_dir
    return root / MATCH_STATS_PARQUET


def load_match_stats(event_id: int, *, output_dir: Path | None = None) -> dict[str, Any] | None:
    from ingest.sofascore.stats_dataset import load_raw_match_stats_df

    df = load_raw_match_stats_df(stats_dir=output_dir)
    if df.empty:
        return None
    rows = df[df["event_id"] == event_id]
    if rows.empty:
        return None
    return rows.iloc[-1].to_dict()


def ingest_match_stats(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
    save: bool = True,
    output_dir: Path | None = None,
    include_incidents: bool = True,
) -> MatchStatsIngestResult:
    result = build_match_stats_payload(
        home_team=home_team,
        away_team=away_team,
        event_id=event_id,
        match_date=match_date,
        client=client,
        team_map=team_map,
        include_incidents=include_incidents,
    )
    payload = result.to_payload()
    json_path = None
    parquet_path = None
    if save:
        json_path = save_match_stats_json(payload, output_dir=output_dir)
        parquet_path = upsert_match_stats_parquet(payload, output_dir=output_dir)
    return MatchStatsIngestResult(
        event_id=result.event_id,
        home_team=result.home_team,
        away_team=result.away_team,
        match_date=result.match_date,
        stats=result.stats,
        json_path=json_path,
        parquet_path=parquet_path,
    )


def _update_stats_json_match_date(
    stats_dir: Path,
    event_id: int,
    match_date: str,
) -> bool:
    matches = list(stats_dir.glob(f"{event_id}_*_stats.json"))
    if not matches:
        return False
    for path in matches:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["match_date"] = match_date
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def backfill_match_dates(
    *,
    client: SofascoreClient | None = None,
    output_dir: Path | None = None,
    limit: int | None = None,
    update_json: bool = True,
) -> dict[str, int]:
    from ingest.gcp.lake_store import cloud_lake_enabled
    from ingest.sofascore.event_helpers import match_date_from_event
    from ingest.sofascore.stats_dataset import load_raw_match_stats_df, save_raw_match_stats_df

    df = load_raw_match_stats_df(stats_dir=output_dir).copy()
    if df.empty:
        return {"total": 0, "updated": 0, "skipped": 0, "failed": 0}

    missing_mask = df["match_date"].isna() | (df["match_date"].astype(str).str.strip() == "")
    targets = df[missing_mask]
    if limit is not None:
        targets = targets.head(limit)

    sofascore = client or SofascoreClient()
    updated = skipped = failed = 0

    for idx, row in targets.iterrows():
        event_id = int(row["event_id"])
        try:
            event = sofascore.event(event_id)
            date_str = match_date_from_event(event)
            if not date_str:
                skipped += 1
                continue
            df.at[idx, "match_date"] = date_str
            updated += 1
            if update_json and not cloud_lake_enabled():
                root = output_dir or settings.sofascore_stats_dir
                _update_stats_json_match_date(root, event_id, date_str)
        except Exception as exc:
            failed += 1
            logger.warning(
                "sofascore_backfill_date_failed",
                event_id=event_id,
                error=str(exc),
            )

    df["match_date"] = pd.to_datetime(df["match_date"], utc=True, errors="coerce")
    save_raw_match_stats_df(df, stats_dir=output_dir)
    logger.info(
        "sofascore_backfill_dates_complete",
        total=len(targets),
        updated=updated,
        skipped=skipped,
        failed=failed,
    )
    return {
        "total": len(targets),
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


def ingest_fept_and_stats(
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    event_id: int | None = None,
    match_date: date | None = None,
    save: bool = True,
    fept_dir: Path | None = None,
    stats_dir: Path | None = None,
) -> tuple[Any, Path | None, MatchStatsIngestResult]:
    """FEPT + estatísticas no mesmo event_id."""
    from ingest.sofascore.fept_ingest import ingest_fept

    fept_result, fept_path = ingest_fept(
        home_team=home_team,
        away_team=away_team,
        event_id=event_id,
        match_date=match_date,
        save=save,
        output_dir=fept_dir,
    )
    stats_result = ingest_match_stats(
        event_id=fept_result.event_id,
        home_team=fept_result.home_team,
        away_team=fept_result.away_team,
        match_date=match_date,
        save=save,
        output_dir=stats_dir,
    )
    return fept_result, fept_path, stats_result
