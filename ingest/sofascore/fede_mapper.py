from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ingest.sofascore.fept_mapper import resolve_player_rating
from schemas.wc_kxl_dynamic import FedeDesfalque, FedeElenco

POSITION_TO_FEDE: dict[str, str] = {
    "G": "Zaga",
    "D": "Zaga",
    "M": "Meio",
    "F": "Ataque",
}


def _fede_position(raw: str | None) -> str:
    key = (raw or "M").strip().upper()[:1]
    return POSITION_TO_FEDE.get(key, "Meio")


def _impact_from_rating(rating: float | None) -> tuple[float | None, float | None, float]:
    if rating is None:
        return None, None, 0.04
    nota = round(rating, 2)
    impacto_nota = -round(rating * 0.08, 2)
    impacto = min(0.12, rating / 10.0 * 0.08 + 0.02)
    return nota, impacto_nota, impacto


def map_missing_entry_to_desfalque(
    entry: dict[str, Any],
    *,
    rating_cache: dict[int, float | None],
    fetch_statistics: Callable[[int], list[dict[str, Any]]],
) -> FedeDesfalque:
    player = entry.get("player") or {}
    name = player.get("shortName") or player.get("name") or "Desconhecido"
    rating = resolve_player_rating(
        {"player": player, "statistics": entry.get("statistics")},
        rating_cache=rating_cache,
        fetch_statistics=fetch_statistics,
    )
    nota_elenco, impacto_nota, impacto = _impact_from_rating(rating)

    return FedeDesfalque(
        jogador=name,
        posicao=_fede_position(player.get("position")),
        nota_elenco=nota_elenco,
        impacto_nota_elenco=impacto_nota,
        impacto=impacto,
    )


def map_side_missing_players(
    side_block: dict[str, Any],
    *,
    rating_cache: dict[int, float | None],
    fetch_statistics: Callable[[int], list[dict[str, Any]]],
) -> list[FedeDesfalque]:
    missing = side_block.get("missingPlayers") or []
    return [
        map_missing_entry_to_desfalque(
            entry,
            rating_cache=rating_cache,
            fetch_statistics=fetch_statistics,
        )
        for entry in missing
        if entry.get("player")
    ]


def map_lineups_to_fede(
    lineups: dict[str, Any],
    *,
    home_is_event_home: bool,
    fetch_statistics: Callable[[int], list[dict[str, Any]]],
    rating_cache: dict[int, float | None] | None = None,
) -> FedeElenco:
    cache = rating_cache if rating_cache is not None else {}
    home_block = lineups.get("home") or {}
    away_block = lineups.get("away") or {}

    if home_is_event_home:
        mandante_block, visitante_block = home_block, away_block
    else:
        mandante_block, visitante_block = away_block, home_block

    return FedeElenco(
        desfalques_mandante=map_side_missing_players(
            mandante_block,
            rating_cache=cache,
            fetch_statistics=fetch_statistics,
        ),
        desfalques_visitante=map_side_missing_players(
            visitante_block,
            rating_cache=cache,
            fetch_statistics=fetch_statistics,
        ),
    )
