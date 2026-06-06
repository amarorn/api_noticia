from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from schemas.national_teams import normalize_national_team

DEFAULT_TEAMS_PATH = Path(__file__).resolve().parents[2] / "data" / "wc" / "sofascore_teams.json"

SOFASCORE_SEARCH_NAMES: dict[str, str] = {
    "Alemanha": "Germany",
    "Argélia": "Algeria",
    "Arábia Saudita": "Saudi Arabia",
    "África do Sul": "South Africa",
    "Áustria": "Austria",
    "Austrália": "Australia",
    "Bélgica": "Belgium",
    "Bolívia": "Bolivia",
    "Bósnia": "Bosnia",
    "Brasil": "Brazil",
    "Cabo Verde": "Cape Verde",
    "Camarões": "Cameroon",
    "Canadá": "Canada",
    "Catar": "Qatar",
    "Chile": "Chile",
    "Colômbia": "Colombia",
    "Coreia do Sul": "South Korea",
    "Costa do Marfim": "Ivory Coast",
    "Costa Rica": "Costa Rica",
    "Croácia": "Croatia",
    "Curaçau": "Curacao",
    "Dinamarca": "Denmark",
    "Egito": "Egypt",
    "Equador": "Ecuador",
    "Escócia": "Scotland",
    "Espanha": "Spain",
    "Estados Unidos": "USA",
    "França": "France",
    "Gana": "Ghana",
    "Haiti": "Haiti",
    "Holanda": "Netherlands",
    "Honduras": "Honduras",
    "Inglaterra": "England",
    "Irã": "Iran",
    "Iraque": "Iraq",
    "Islândia": "Iceland",
    "Itália": "Italy",
    "Jamaica": "Jamaica",
    "Japão": "Japan",
    "Jordânia": "Jordan",
    "Marrocos": "Morocco",
    "México": "Mexico",
    "Nigéria": "Nigeria",
    "Noruega": "Norway",
    "Nova Zelândia": "New Zealand",
    "Panamá": "Panama",
    "Paraguai": "Paraguay",
    "Peru": "Peru",
    "Polônia": "Poland",
    "Portugal": "Portugal",
    "República Democrática do Congo": "DR Congo",
    "República Tcheca": "Czech Republic",
    "Romênia": "Romania",
    "Senegal": "Senegal",
    "Suécia": "Sweden",
    "Suíça": "Switzerland",
    "Tunísia": "Tunisia",
    "Turquia": "Turkey",
    "Ucrânia": "Ukraine",
    "Uruguai": "Uruguay",
    "Uzbequistão": "Uzbekistan",
    "Venezuela": "Venezuela",
}


@lru_cache(maxsize=1)
def load_team_map(path: str | None = None) -> dict[str, dict]:
    file_path = Path(path) if path else DEFAULT_TEAMS_PATH
    if not file_path.exists():
        return {}
    data = json.loads(file_path.read_text(encoding="utf-8"))
    teams = data.get("teams") or {}
    return {normalize_national_team(name): meta for name, meta in teams.items()}


def sofascore_search_query(team_name: str) -> str:
    canonical = normalize_national_team(team_name)
    return SOFASCORE_SEARCH_NAMES.get(canonical, canonical)


def resolve_team_id(
    team_name: str,
    *,
    team_map: dict[str, dict] | None = None,
    client=None,
) -> tuple[int, str]:
    canonical = normalize_national_team(team_name)
    mapping = team_map if team_map is not None else load_team_map()
    entry = mapping.get(canonical)
    if entry and entry.get("sofascore_id"):
        return int(entry["sofascore_id"]), canonical

    if client is None:
        raise KeyError(
            f"Seleção '{canonical}' sem mapeamento em data/wc/sofascore_teams.json"
        )

    entity = client.search_team(sofascore_search_query(canonical))
    if not entity or not entity.get("id"):
        raise KeyError(f"Seleção '{canonical}' não encontrada no Sofascore")
    return int(entity["id"]), canonical


def event_team_ids(event: dict) -> tuple[int, int]:
    home_id = int((event.get("homeTeam") or {}).get("id"))
    away_id = int((event.get("awayTeam") or {}).get("id"))
    return home_id, away_id


def event_team_names(event: dict) -> tuple[str, str]:
    home = (event.get("homeTeam") or {}).get("name") or ""
    away = (event.get("awayTeam") or {}).get("name") or ""
    return home, away


def sides_for_event(
    event: dict,
    *,
    home_team: str,
    away_team: str,
    team_map: dict[str, dict] | None = None,
) -> tuple[bool, int, int]:
    """Retorna (home_is_event_home, home_sofascore_id, away_sofascore_id)."""
    home_id, _ = resolve_team_id(home_team, team_map=team_map)
    away_id, _ = resolve_team_id(away_team, team_map=team_map)
    event_home_id, event_away_id = event_team_ids(event)
    if event_home_id == home_id and event_away_id == away_id:
        return True, home_id, away_id
    if event_home_id == away_id and event_away_id == home_id:
        return False, home_id, away_id
    raise ValueError(
        f"Evento {event.get('id')} não corresponde a {home_team} x {away_team}"
    )
