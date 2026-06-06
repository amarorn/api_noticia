from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from config import settings
from ingest.sofascore.client import SofascoreClient
from ingest.sofascore.event_helpers import canonical_from_event_team, match_date_from_event
from ingest.sofascore.teams import load_team_map, resolve_team_id
from schemas.national_teams import normalize_national_team

logger = structlog.get_logger()

FRIENDLY_SLUG_TOKENS = (
    "international-friendly",
    "int-friendly-games",
    "friendlies",
    "friendly-games",
    "amistoso",
)


def tournament_slug(event: dict[str, Any]) -> str:
    tournament = event.get("tournament") or event.get("uniqueTournament") or {}
    return str(tournament.get("slug") or "").lower()


def tournament_name(event: dict[str, Any]) -> str:
    tournament = event.get("tournament") or event.get("uniqueTournament") or {}
    return str(tournament.get("name") or "")


def is_friendly_event(event: dict[str, Any]) -> bool:
    slug = tournament_slug(event)
    if any(token in slug for token in FRIENDLY_SLUG_TOKENS):
        return True
    name = tournament_name(event).lower()
    return "friendly" in name or "amistoso" in name


def event_status(event: dict[str, Any]) -> str:
    status = event.get("status") or {}
    code = status.get("code")
    raw_type = str(status.get("type") or "").lower()
    if code == 100 or raw_type == "finished":
        return "finished"
    if raw_type in {"inprogress", "live"}:
        return "live"
    if raw_type in {"notstarted", "postponed", "canceled", "cancelled"}:
        return raw_type
    return raw_type or "unknown"


def match_year(match_date: str | None) -> int | None:
    if not match_date:
        return None
    try:
        return datetime.fromisoformat(match_date.replace("Z", "+00:00")).year
    except ValueError:
        return None


def _event_score(event: dict[str, Any], side: str) -> int | None:
    payload = event.get(f"{side}Score") or {}
    current = payload.get("current")
    if current is None:
        return None
    try:
        return int(current)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class FriendlyMatch:
    home_team: str
    away_team: str
    match_date: str | None
    status: str
    home_score: int | None
    away_score: int | None
    tournament: str
    is_home: bool
    event_id: int | None = None
    fifa_match_id: str | None = None
    sources: tuple[str, ...] = ("sofascore",)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "fifa_match_id": self.fifa_match_id,
            "sources": list(self.sources),
            "home_team": self.home_team,
            "away_team": self.away_team,
            "match_date": self.match_date,
            "status": self.status,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "tournament": self.tournament,
            "is_home": self.is_home,
        }


def map_friendly_event(
    event: dict[str, Any],
    *,
    team: str,
    team_map: dict[str, dict],
) -> FriendlyMatch | None:
    if not is_friendly_event(event):
        return None

    canonical = normalize_national_team(team)
    home = canonical_from_event_team(event.get("homeTeam") or {}, team_map)
    away = canonical_from_event_team(event.get("awayTeam") or {}, team_map)
    if canonical not in {home, away}:
        return None

    return FriendlyMatch(
        home_team=home,
        away_team=away,
        match_date=match_date_from_event(event),
        status=event_status(event),
        home_score=_event_score(event, "home"),
        away_score=_event_score(event, "away"),
        tournament=tournament_name(event) or "Amistoso internacional",
        is_home=canonical == home,
        event_id=int(event["id"]),
        sources=("sofascore",),
    )


def _match_day_key(home: str, away: str, match_date: str | None) -> str:
    day = ""
    if match_date:
        day = match_date[:10]
    pair = tuple(sorted([normalize_national_team(home), normalize_national_team(away)]))
    return f"{pair[0]}|{pair[1]}|{day}"


def merge_friendlies(
    sofascore_rows: list[FriendlyMatch],
    fifa_rows: list[FriendlyMatch],
) -> list[FriendlyMatch]:
    merged: dict[str, FriendlyMatch] = {}

    for row in sofascore_rows:
        merged[_match_day_key(row.home_team, row.away_team, row.match_date)] = row

    for fifa_row in fifa_rows:
        key = _match_day_key(fifa_row.home_team, fifa_row.away_team, fifa_row.match_date)
        existing = merged.get(key)
        if existing is None:
            merged[key] = fifa_row
            continue
        sources = tuple(dict.fromkeys((*existing.sources, "fifa")))
        merged[key] = FriendlyMatch(
            home_team=existing.home_team,
            away_team=existing.away_team,
            match_date=existing.match_date or fifa_row.match_date,
            status=existing.status,
            home_score=existing.home_score if existing.home_score is not None else fifa_row.home_score,
            away_score=existing.away_score if existing.away_score is not None else fifa_row.away_score,
            tournament=existing.tournament or fifa_row.tournament,
            is_home=existing.is_home,
            event_id=existing.event_id,
            fifa_match_id=fifa_row.fifa_match_id,
            sources=sources,
        )

    rows = list(merged.values())
    rows.sort(key=lambda item: item.match_date or "", reverse=True)
    return rows


def _append_friendly_events(
    events: list[dict[str, Any]],
    *,
    team: str,
    team_map: dict[str, dict],
    filter_year: int,
    include_finished: bool,
    include_upcoming: bool,
    seen: set[int],
    friendlies: list[FriendlyMatch],
) -> None:
    for event in events:
        event_id = int(event["id"])
        if event_id in seen:
            continue
        seen.add(event_id)

        mapped = map_friendly_event(event, team=team, team_map=team_map)
        if mapped is None:
            continue

        if mapped.status == "finished" and not include_finished:
            continue
        if mapped.status != "finished" and not include_upcoming:
            continue
        if match_year(mapped.match_date) != filter_year:
            continue
        friendlies.append(mapped)


def list_team_friendlies(
    team: str,
    *,
    pages: int = 2,
    upcoming_pages: int = 2,
    year: int | None = None,
    include_finished: bool = True,
    include_upcoming: bool = True,
    client: SofascoreClient | None = None,
    team_map: dict[str, dict] | None = None,
) -> list[FriendlyMatch]:
    """Lista amistosos recentes e futuros de uma seleção via Sofascore."""
    filter_year = year if year is not None else datetime.now(timezone.utc).year
    team_map = team_map if team_map is not None else load_team_map()
    sofascore = client or SofascoreClient()
    canonical = normalize_national_team(team)
    team_id, _ = resolve_team_id(canonical, team_map=team_map, client=sofascore)

    seen: set[int] = set()
    friendlies: list[FriendlyMatch] = []

    if include_upcoming:
        for page in range(max(1, upcoming_pages)):
            events = sofascore.team_upcoming_events(team_id, page=page)
            if not events:
                break
            _append_friendly_events(
                events,
                team=canonical,
                team_map=team_map,
                filter_year=filter_year,
                include_finished=include_finished,
                include_upcoming=include_upcoming,
                seen=seen,
                friendlies=friendlies,
            )

    if include_finished or include_upcoming:
        for page in range(max(1, pages)):
            events = sofascore.team_recent_events(team_id, page=page)
            if not events:
                break
            _append_friendly_events(
                events,
                team=canonical,
                team_map=team_map,
                filter_year=filter_year,
                include_finished=include_finished,
                include_upcoming=include_upcoming,
                seen=seen,
                friendlies=friendlies,
            )

    from ingest.fifa.friendlies import list_fifa_team_friendlies

    try:
        fifa_rows = list_fifa_team_friendlies(
            canonical,
            year=filter_year,
        )
    except Exception as exc:
        logger.warning("fifa_friendlies_merge_skipped", team=canonical, error=str(exc))
        fifa_rows = []
    if include_finished is False:
        fifa_rows = [row for row in fifa_rows if row.status != "finished"]
    if include_upcoming is False:
        fifa_rows = [row for row in fifa_rows if row.status == "finished"]

    return merge_friendlies(friendlies, fifa_rows)


def save_friendlies_snapshot(
    team: str,
    year: int,
    friendlies: list[FriendlyMatch],
    *,
    output_dir: Path | None = None,
) -> Path:
    """Atualiza snapshot local do lake (uma entrada por seleção consultada)."""
    root = output_dir or (settings.lake_root / "friendlies")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{year}.json"
    payload: dict[str, Any] = {}
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = normalize_national_team(team)
    payload[canonical] = {
        "team": canonical,
        "year": year,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(friendlies),
        "friendlies": [row.to_dict() for row in friendlies],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_friendlies_snapshot(
    team: str,
    year: int,
    *,
    output_dir: Path | None = None,
) -> list[FriendlyMatch] | None:
    root = output_dir or (settings.lake_root / "friendlies")
    path = root / f"{year}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    canonical = normalize_national_team(team)
    block = payload.get(canonical)
    if not block:
        return None
    return [
        FriendlyMatch(
            home_team=str(row["home_team"]),
            away_team=str(row["away_team"]),
            match_date=row.get("match_date"),
            status=str(row["status"]),
            home_score=row.get("home_score"),
            away_score=row.get("away_score"),
            tournament=str(row.get("tournament") or "Amistoso internacional"),
            is_home=bool(row.get("is_home")),
            event_id=int(row["event_id"]) if row.get("event_id") else None,
            fifa_match_id=row.get("fifa_match_id"),
            sources=tuple(row.get("sources") or ["sofascore"]),
        )
        for row in block.get("friendlies") or []
    ]
