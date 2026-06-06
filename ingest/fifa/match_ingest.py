from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from config import settings
from ingest.fifa.client import FifaClient

logger = structlog.get_logger()


@dataclass(frozen=True)
class FifaGoal:
    minute: str
    player_name: str
    player_id: str
    team_id: str
    assist_player_id: str | None
    goal_type: int  # 1=?, 2=normal, 3=contra
    period: int  # 3=1T, 5=2T


@dataclass(frozen=True)
class FifaBooking:
    minute: str
    player_id: str
    player_name: str
    card_type: int  # 1=amarelo, 2=vermelho?
    reason: str
    period: int


@dataclass(frozen=True)
class FifaSubstitution:
    minute: str
    player_off_id: str
    player_off_name: str
    player_on_id: str
    player_on_name: str
    period: int


@dataclass(frozen=True)
class FifaPlayer:
    id: str
    name: str
    short_name: str
    shirt_number: int
    position: int  # 0=GK, 1=DEF, 2=MID, 3=FWD
    is_captain: bool
    status: int  # 1=titular?
    field_status: int  # 1=em campo, 2=fora?
    picture_url: str | None


@dataclass(frozen=True)
class FifaTeamLineup:
    team_id: str
    team_name: str
    country_code: str
    score: int
    tactics: str | None
    coach: str | None
    players: list[FifaPlayer]
    goals: list[FifaGoal]
    bookings: list[FifaBooking]
    substitutions: list[FifaSubstitution]


@dataclass(frozen=True)
class FifaMatchDetails:
    match_id: str
    date: str
    competition: str
    season: str
    stage: str
    group: str | None
    stadium: str | None
    city: str | None
    attendance: int | None
    home_team: FifaTeamLineup
    away_team: FifaTeamLineup
    winner_id: str | None
    match_status: int
    period: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "date": self.date,
            "competition": self.competition,
            "season": self.season,
            "stage": self.stage,
            "group": self.group,
            "stadium": self.stadium,
            "city": self.city,
            "attendance": self.attendance,
            "winner_id": self.winner_id,
            "match_status": self.match_status,
            "period": self.period,
            "home_team": {
                "team_id": self.home_team.team_id,
                "team_name": self.home_team.team_name,
                "country_code": self.home_team.country_code,
                "score": self.home_team.score,
                "tactics": self.home_team.tactics,
                "coach": self.home_team.coach,
                "players": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "short_name": p.short_name,
                        "shirt_number": p.shirt_number,
                        "position": p.position,
                        "is_captain": p.is_captain,
                        "status": p.status,
                        "field_status": p.field_status,
                        "picture_url": p.picture_url,
                    }
                    for p in self.home_team.players
                ],
                "goals": [
                    {
                        "minute": g.minute,
                        "player_name": g.player_name,
                        "player_id": g.player_id,
                        "assist_player_id": g.assist_player_id,
                        "goal_type": g.goal_type,
                        "period": g.period,
                    }
                    for g in self.home_team.goals
                ],
                "bookings": [
                    {
                        "minute": b.minute,
                        "player_name": b.player_name,
                        "player_id": b.player_id,
                        "card_type": b.card_type,
                        "reason": b.reason,
                        "period": b.period,
                    }
                    for b in self.home_team.bookings
                ],
                "substitutions": [
                    {
                        "minute": s.minute,
                        "player_off_name": s.player_off_name,
                        "player_off_id": s.player_off_id,
                        "player_on_name": s.player_on_name,
                        "player_on_id": s.player_on_id,
                        "period": s.period,
                    }
                    for s in self.home_team.substitutions
                ],
            },
            "away_team": {
                "team_id": self.away_team.team_id,
                "team_name": self.away_team.team_name,
                "country_code": self.away_team.country_code,
                "score": self.away_team.score,
                "tactics": self.away_team.tactics,
                "coach": self.away_team.coach,
                "players": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "short_name": p.short_name,
                        "shirt_number": p.shirt_number,
                        "position": p.position,
                        "is_captain": p.is_captain,
                        "status": p.status,
                        "field_status": p.field_status,
                        "picture_url": p.picture_url,
                    }
                    for p in self.away_team.players
                ],
                "goals": [
                    {
                        "minute": g.minute,
                        "player_name": g.player_name,
                        "player_id": g.player_id,
                        "assist_player_id": g.assist_player_id,
                        "goal_type": g.goal_type,
                        "period": g.period,
                    }
                    for g in self.away_team.goals
                ],
                "bookings": [
                    {
                        "minute": b.minute,
                        "player_name": b.player_name,
                        "player_id": b.player_id,
                        "card_type": b.card_type,
                        "reason": b.reason,
                        "period": b.period,
                    }
                    for b in self.away_team.bookings
                ],
                "substitutions": [
                    {
                        "minute": s.minute,
                        "player_off_name": s.player_off_name,
                        "player_off_id": s.player_off_id,
                        "player_on_name": s.player_on_name,
                        "player_on_id": s.player_on_id,
                        "period": s.period,
                    }
                    for s in self.away_team.substitutions
                ],
            },
        }


def _extract_name(names: list[dict]) -> str:
    for n in names:
        if n.get("Locale", "").lower().startswith("pt"):
            return n.get("Description", "")
    for n in names:
        if n.get("Locale", "").lower().startswith("en"):
            return n.get("Description", "")
    return names[0].get("Description", "") if names else ""


def _parse_goals(raw_goals: list[dict], team_id: str) -> list[FifaGoal]:
    goals = []
    for g in raw_goals:
        goals.append(
            FifaGoal(
                minute=g.get("Minute", ""),
                player_name=g.get("PlayerName", [{}])[0].get("Description", "")
                if g.get("PlayerName")
                else "",
                player_id=g.get("IdPlayer", ""),
                team_id=team_id,
                assist_player_id=g.get("IdAssistPlayer") or None,
                goal_type=g.get("Type", 2),
                period=g.get("Period", 0),
            )
        )
    return goals


def _parse_bookings(raw_bookings: list[dict], team_id: str) -> list[FifaBooking]:
    bookings = []
    for b in raw_bookings:
        bookings.append(
            FifaBooking(
                minute=b.get("Minute", ""),
                player_id=b.get("IdPlayer", ""),
                player_name=b.get("PlayerName", [{}])[0].get("Description", "")
                if b.get("PlayerName")
                else "",
                card_type=b.get("Card", 1),
                reason=b.get("Reason", ""),
                period=b.get("Period", 0),
            )
        )
    return bookings


def _parse_substitutions(raw_subs: list[dict]) -> list[FifaSubstitution]:
    subs = []
    for s in raw_subs:
        subs.append(
            FifaSubstitution(
                minute=s.get("Minute", ""),
                player_off_id=s.get("IdPlayerOff", ""),
                player_off_name=_extract_name(s.get("PlayerOffName", [])),
                player_on_id=s.get("IdPlayerOn", ""),
                player_on_name=_extract_name(s.get("PlayerOnName", [])),
                period=s.get("Period", 0),
            )
        )
    return subs


def _parse_players(raw_players: list[dict]) -> list[FifaPlayer]:
    players = []
    for p in raw_players:
        pic = p.get("PlayerPicture")
        players.append(
            FifaPlayer(
                id=p.get("IdPlayer", ""),
                name=_extract_name(p.get("PlayerName", [])),
                short_name=_extract_name(p.get("ShortName", [])),
                shirt_number=p.get("ShirtNumber", 0),
                position=p.get("Position", 0),
                is_captain=bool(p.get("Captain", False)),
                status=p.get("Status", 1),
                field_status=p.get("FieldStatus", 1),
                picture_url=pic.get("PictureUrl") if pic else None,
            )
        )
    return players


def _parse_team(data: dict[str, Any]) -> FifaTeamLineup:
    coach = ""
    coaches = data.get("Coaches", [])
    for c in coaches:
        if c.get("Role") == 0:  # head coach
            coach = _extract_name(c.get("Name", []))
            break
    if not coach and coaches:
        coach = _extract_name(coaches[0].get("Name", []))

    return FifaTeamLineup(
        team_id=data.get("IdTeam", ""),
        team_name=_extract_name(data.get("TeamName", [])),
        country_code=data.get("IdCountry", ""),
        score=data.get("Score", 0),
        tactics=data.get("Tactics") or None,
        coach=coach or None,
        players=_parse_players(data.get("Players", [])),
        goals=_parse_goals(data.get("Goals", []), data.get("IdTeam", "")),
        bookings=_parse_bookings(data.get("Bookings", []), data.get("IdTeam", "")),
        substitutions=_parse_substitutions(data.get("Substitutions", [])),
    )


def ingest_match_details(match_id: str, client: FifaClient | None = None) -> FifaMatchDetails:
    """Busca e parseia detalhes completos de um jogo da FIFA."""
    fifa = client or FifaClient()
    raw = fifa.match_details(match_id)

    home_team = _parse_team(raw.get("HomeTeam", {}))
    away_team = _parse_team(raw.get("AwayTeam", {}))

    stadium_data = raw.get("Stadium", {}) or {}
    city_data = stadium_data.get("CityName", [])
    city = _extract_name(city_data) if city_data else None

    competition = _extract_name(raw.get("CompetitionName", []))
    season = _extract_name(raw.get("SeasonName", []))
    stage = _extract_name(raw.get("StageName", []))
    group = _extract_name(raw.get("GroupName", [])) if raw.get("GroupName") else None

    attendance = raw.get("Attendance")
    if attendance is not None:
        try:
            attendance = int(str(attendance).replace(",", "").replace(".", ""))
        except ValueError:
            attendance = None

    return FifaMatchDetails(
        match_id=match_id,
        date=raw.get("Date", ""),
        competition=competition,
        season=season,
        stage=stage,
        group=group,
        stadium=_extract_name(stadium_data.get("Name", [])) if stadium_data else None,
        city=city,
        attendance=attendance,
        home_team=home_team,
        away_team=away_team,
        winner_id=raw.get("Winner"),
        match_status=raw.get("MatchStatus", 0),
        period=raw.get("Period", 0),
    )


def save_match_details(details: FifaMatchDetails, *, output_dir: Path | None = None) -> Path:
    root = output_dir or settings.fifa_matches_dir
    root.mkdir(parents=True, exist_ok=True)

    home = details.home_team.team_name.replace(" ", "-") if details.home_team.team_name else "home"
    away = details.away_team.team_name.replace(" ", "-") if details.away_team.team_name else "away"
    path = root / f"{details.match_id}_{home}_x_{away}.json"
    path.write_text(
        json.dumps(details.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _flatten_window_matches(data: dict[str, Any]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for team_data in data.get("matches", {}).values():
        for match in team_data.get("MatchesList", []):
            matches.append(match)
    return matches


def _read_window_cache(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            cached = payload.get("matches")
            if isinstance(cached, list):
                return cached
    except Exception as exc:
        logger.warning("fifa_window_cache_read_failed", error=str(exc))
    return None


def _write_window_cache(path: Path, matches: list[dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"matches": matches}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("fifa_window_cache_save_failed", error=str(exc))


def load_fifa_window_matches(
    *,
    gender: int = 1,
    ranking_type: int = 0,
    force_refresh: bool = False,
    client: FifaClient | None = None,
    max_cache_age_hours: float = 24.0,
) -> list[dict[str, Any]]:
    """Carrega jogos da janela FIFA com cache local e fallback offline."""
    from datetime import datetime, timezone

    cache_path = settings.fifa_window_cache_path

    if not force_refresh and cache_path.is_file():
        try:
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
            if age_hours < max_cache_age_hours:
                cached = _read_window_cache(cache_path)
                if cached is not None:
                    logger.info(
                        "fifa_window_matches_loaded_from_cache",
                        count=len(cached),
                        age_hours=round(age_hours, 1),
                    )
                    return cached
        except Exception as exc:
            logger.warning("fifa_window_cache_error", error=str(exc))

    fifa = client or FifaClient()
    try:
        data = fifa.match_window_matches(gender=gender, ranking_type=ranking_type)
        matches = _flatten_window_matches(data)
        logger.info("fifa_window_matches_fetched", count=len(matches), gender=gender)
        _write_window_cache(cache_path, matches)
        return matches
    except Exception as exc:
        logger.warning("fifa_window_matches_fetch_failed", error=str(exc))
        cached = _read_window_cache(cache_path)
        if cached is not None:
            logger.info("fifa_window_matches_using_stale_cache", count=len(cached))
            return cached
        return []


def ingest_window_matches(
    *,
    gender: int = 1,
    ranking_type: int = 0,
    client: FifaClient | None = None,
) -> list[dict[str, Any]]:
    """Busca todos os jogos da janela atual de rankings FIFA.

    Retorna lista flatten com todos os jogos encontrados.
    """
    return load_fifa_window_matches(gender=gender, ranking_type=ranking_type, client=client)
