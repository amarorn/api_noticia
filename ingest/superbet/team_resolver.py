"""Classificação e normalização de times ao vivo (clubes vs seleções)."""
from __future__ import annotations

from ingest.fifa.teams import FIFA_COUNTRY_CODES
from schemas.national_teams import NATIONAL_ALIASES, normalize_national_team
from schemas.teams import BRAZILIAN_TEAMS, normalize_team

MatchKind = str  # "club" | "national" | "other"

_CLUB_MARKERS = (
    " fc",
    " fa",
    " juniors",
    " kopavog",
    "(f)",
    " united fc",
    " city",
    " town",
    " athletic",
    " wanderers",
    " rovers",
    " deportivo",
    " club ",
)


def looks_like_club(name: str) -> bool:
    low = name.lower()
    if any(marker in low for marker in _CLUB_MARKERS):
        return True
    if " united" in low and "estados unidos" not in low:
        return True
    return False


def is_brazilian_club(name: str) -> bool:
    return normalize_team(name) in BRAZILIAN_TEAMS


def is_wc_national_team(name: str) -> bool:
    """Compat: seleção reconhecida pelo normalizador FIFA."""
    norm = normalize_national_team(name)
    known = set(FIFA_COUNTRY_CODES.keys()) | set(NATIONAL_ALIASES.values())
    return norm in known and not looks_like_club(name)


def is_international_match(home_team: str, away_team: str) -> bool:
    """Heurística: amistoso/seleção vs seleção (exclui clubes óbvios)."""
    if looks_like_club(home_team) or looks_like_club(away_team):
        return False
    known = set(FIFA_COUNTRY_CODES.keys()) | set(NATIONAL_ALIASES.values())
    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    return home in known and away in known


def resolve_live_team(raw: str) -> str:
    """Normaliza nome Superbet → clube BR ou seleção."""
    club = normalize_team(raw)
    if club in BRAZILIAN_TEAMS:
        return club
    national = normalize_national_team(raw)
    if national in set(FIFA_COUNTRY_CODES.keys()) | set(NATIONAL_ALIASES.values()):
        return national
    return club


def classify_live_match(home_raw: str, away_raw: str) -> tuple[str, str, MatchKind]:
    home = resolve_live_team(home_raw)
    away = resolve_live_team(away_raw)

    if is_international_match(home_raw, away_raw):
        return home, away, "national"

    if (
        looks_like_club(home_raw)
        or looks_like_club(away_raw)
        or is_brazilian_club(home)
        or is_brazilian_club(away)
    ):
        return home, away, "club"

    return home, away, "other"


def resolve_club_competition(home: str, away: str) -> str:
    """Competição de fixtures para in-play de clubes; vazio = prior de mercado."""
    br_home = is_brazilian_club(home)
    br_away = is_brazilian_club(away)
    if br_home and br_away:
        return "Brasileirão"
    if br_home or br_away:
        return "Copa Libertadores"
    return ""


__all__ = [
    "classify_live_match",
    "is_brazilian_club",
    "is_international_match",
    "is_wc_national_team",
    "looks_like_club",
    "resolve_club_competition",
    "resolve_live_team",
]
