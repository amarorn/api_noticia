"""Resolve Sofascore event id e busca incidents ao vivo para momentum in-play."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import structlog

from config import settings
from ingest.sofascore.live_events import live_events_as_dicts
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()


def _live_bronze_dir(sofascore_event_id: int) -> Path:
    return settings.bronze_path / "sofascore" / "live" / str(sofascore_event_id)


def save_live_incidents_snapshot(
    sofascore_event_id: int,
    events: list[dict],
    *,
    home_team: str,
    away_team: str,
) -> Path | None:
    """Persiste incidents ao vivo (bronze) para timeline e retreino."""
    if not events:
        return None
    out_dir = _live_bronze_dir(sofascore_event_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{ts}.json"
    payload = {
        "sofascore_event_id": sofascore_event_id,
        "home_team": home_team,
        "away_team": away_team,
        "captured_at": datetime.now(UTC).isoformat(),
        "n_events": len(events),
        "events": events,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = out_dir / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def resolve_sofascore_event_id(
    home_team: str,
    away_team: str,
    *,
    match_date: date | None = None,
    waf_max_retries: int | None = None,
) -> int | None:
    """Resolve event_id Sofascore por seleções + data (falha silenciosa)."""
    try:
        from ingest.sofascore.client import SofascoreClient
        from ingest.sofascore.event_helpers import find_event_id
        from ingest.sofascore.teams import load_team_map

        when = match_date or datetime.now(UTC).date()
        client = SofascoreClient(waf_max_retries=waf_max_retries)
        team_map = load_team_map()
        for offset in (0, -1, 1):
            probe = when + timedelta(days=offset)
            try:
                event = find_event_id(
                    client,
                    home_team=normalize_national_team(home_team),
                    away_team=normalize_national_team(away_team),
                    match_date=probe,
                    team_map=team_map,
                )
                return int(event["id"])
            except LookupError:
                continue
    except Exception as exc:
        logger.warning(
            "sofascore_event_resolve_falha",
            home=home_team,
            away=away_team,
            error=str(exc),
        )
    return None


def enrich_momentum_from_sofascore(
    home_team: str,
    away_team: str,
    *,
    match_date: date | None = None,
    save_bronze: bool = True,
    waf_max_retries: int | None = None,
) -> tuple[list[dict], int | None]:
    """Busca gols/cartões/subs Sofascore e retorna dicts para momentum_events."""
    event_id = resolve_sofascore_event_id(
        home_team,
        away_team,
        match_date=match_date,
        waf_max_retries=waf_max_retries,
    )
    if event_id is None:
        return [], None

    events = live_events_as_dicts(event_id)
    if save_bronze and events:
        save_live_incidents_snapshot(
            event_id,
            events,
            home_team=home_team,
            away_team=away_team,
        )
    return events, event_id
