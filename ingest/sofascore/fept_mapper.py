from __future__ import annotations

from typing import Any

from schemas.wc_kxl_dynamic import FeptEscalacao, FeptTitularesEstruturados

POSITION_LINE = {
    "G": "goleiro",
    "D": "defesa",
    "M": "meio",
    "F": "ataque",
}

TOURNAMENT_PRIORITY = (
    "world-championship",
    "european-championship",
    "copa-america",
    "international-friendly",
    "world-championship-qual",
    "uefa-nations-league",
    "conmebol-nations-league",
    "laliga",
    "premier-league",
    "bundesliga",
    "serie-a",
    "ligue-1",
    "brasileirao",
    "eredivisie",
    "primeira-liga",
)


def _line_from_position(position: str | None) -> str:
    key = (position or "M").strip().upper()[:1]
    return POSITION_LINE.get(key, "meio")


def _lineup_rating(entry: dict[str, Any]) -> float | None:
    for key in ("rating", "averageRating"):
        value = entry.get(key)
        if value is not None:
            return float(value)
    stats = entry.get("statistics") or {}
    value = stats.get("rating")
    if value is not None:
        return float(value)
    return None


def _season_priority(season_row: dict[str, Any]) -> tuple[int, int, float]:
    tournament = season_row.get("uniqueTournament") or {}
    slug = str(tournament.get("slug") or "").lower()
    priority = len(TOURNAMENT_PRIORITY)
    for idx, token in enumerate(TOURNAMENT_PRIORITY):
        if token in slug:
            priority = idx
            break
    stats = season_row.get("statistics") or {}
    count_rating = int(stats.get("countRating") or 0)
    rating = float(stats.get("rating") or 0.0)
    return priority, -count_rating, -rating


def pick_player_rating_from_statistics(seasons: list[dict[str, Any]]) -> float | None:
    candidates: list[tuple[tuple[int, int, float], float]] = []
    for row in seasons:
        stats = row.get("statistics") or {}
        rating = stats.get("rating")
        count_rating = stats.get("countRating") or 0
        if rating is None or int(count_rating) < 3:
            continue
        candidates.append((_season_priority(row), float(rating)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def resolve_player_rating(
    entry: dict[str, Any],
    *,
    rating_cache: dict[int, float | None],
    fetch_statistics,
) -> float | None:
    rating = _lineup_rating(entry)
    if rating is not None:
        return rating

    player = entry.get("player") or {}
    player_id = player.get("id")
    if player_id is None:
        return None
    pid = int(player_id)
    if pid in rating_cache:
        return rating_cache[pid]

    seasons = fetch_statistics(pid)
    rating_cache[pid] = pick_player_rating_from_statistics(seasons)
    return rating_cache[pid]


def _player_payload(entry: dict[str, Any], rating: float | None) -> dict[str, Any]:
    player = entry.get("player") or {}
    position = entry.get("position") or player.get("position")
    payload = {
        "nome": player.get("shortName") or player.get("name") or "Desconhecido",
        "posicao": position,
    }
    if rating is not None:
        payload["nota_sofascore"] = round(rating, 2)
    return payload


def map_side_to_structured(
    side_block: dict[str, Any],
    *,
    rating_cache: dict[int, float | None],
    fetch_statistics,
) -> FeptTitularesEstruturados:
    players = [
        entry
        for entry in (side_block.get("players") or [])
        if entry.get("substitute") is False
    ]
    goleiro = None
    defensores: list[dict] = []
    meio_campistas: list[dict] = []
    atacantes: list[dict] = []

    for entry in players:
        player = entry.get("player") or {}
        position = entry.get("position") or player.get("position")
        line = _line_from_position(position)
        rating = resolve_player_rating(
            entry,
            rating_cache=rating_cache,
            fetch_statistics=fetch_statistics,
        )
        payload = _player_payload(entry, rating)
        if line == "goleiro" and goleiro is None:
            goleiro = payload
        elif line == "defesa":
            defensores.append(payload)
        elif line == "meio":
            meio_campistas.append(payload)
        else:
            atacantes.append(payload)

    return FeptTitularesEstruturados(
        goleiro=goleiro,
        defensores=defensores,
        meio_campistas=meio_campistas,
        atacantes=atacantes,
    )


def map_lineups_to_fept(
    lineups: dict[str, Any],
    *,
    home_is_event_home: bool,
    fetch_statistics,
    rating_cache: dict[int, float | None] | None = None,
) -> FeptEscalacao:
    cache = rating_cache if rating_cache is not None else {}
    home_block = lineups.get("home") or {}
    away_block = lineups.get("away") or {}

    if home_is_event_home:
        mandante_block, visitante_block = home_block, away_block
    else:
        mandante_block, visitante_block = away_block, home_block

    return FeptEscalacao(
        esquema_mandante=mandante_block.get("formation"),
        esquema_visitante=visitante_block.get("formation"),
        mandante_titulares_notas=map_side_to_structured(
            mandante_block,
            rating_cache=cache,
            fetch_statistics=fetch_statistics,
        ),
        visitante_titulares_notas=map_side_to_structured(
            visitante_block,
            rating_cache=cache,
            fetch_statistics=fetch_statistics,
        ),
    )
