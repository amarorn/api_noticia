from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.teams import resolve_team_id
from schemas.national_teams import normalize_national_team
from schemas.wc_kxl_dynamic import FeptEscalacao


def count_fept_ratings(fept: FeptEscalacao) -> tuple[int, int]:
    found = 0
    missing = 0
    for block in (fept.mandante_titulares_notas, fept.visitante_titulares_notas):
        if not block:
            continue
        for raw in (
            [block.goleiro] if block.goleiro else []
        ) + list(block.defensores) + list(block.meio_campistas) + list(block.atacantes):
            if isinstance(raw, dict):
                rating = raw.get("nota_sofascore")
            else:
                rating = getattr(raw, "nota_sofascore", None)
            if rating is None:
                missing += 1
            else:
                found += 1
    return found, missing


def match_date_from_event(event: dict[str, Any]) -> str | None:
    ts = event.get("startTimestamp")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def resolve_match_date(
    event: dict[str, Any],
    match_date: date | None = None,
) -> str | None:
    if match_date is not None:
        return match_date.isoformat()
    return match_date_from_event(event)


def find_event_id(
    client: SofascoreClient,
    *,
    home_team: str,
    away_team: str,
    match_date: date,
    sport: str = "football",
    team_map: dict[str, dict] | None = None,
) -> dict[str, Any]:
    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    home_id, _ = resolve_team_id(home, team_map=team_map, client=client)
    away_id, _ = resolve_team_id(away, team_map=team_map, client=client)

    events = client.scheduled_events(sport, match_date.isoformat())
    for event in events:
        event_home_id, event_away_id = (
            int((event.get("homeTeam") or {}).get("id") or 0),
            int((event.get("awayTeam") or {}).get("id") or 0),
        )
        if {event_home_id, event_away_id} == {home_id, away_id}:
            return event

    raise LookupError(
        f"Jogo não encontrado em {match_date.isoformat()}: {home} x {away}"
    )


def canonical_from_event_team(
    event_team: dict[str, Any],
    team_map: dict[str, dict],
) -> str:
    team_id = int(event_team.get("id") or 0)
    for canonical, meta in team_map.items():
        if int(meta.get("sofascore_id") or 0) == team_id:
            return canonical
    return normalize_national_team(str(event_team.get("name") or ""))
