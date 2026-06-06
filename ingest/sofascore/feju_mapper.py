from __future__ import annotations

from typing import Any

from schemas.wc_kxl_dynamic import FejuArbitro

DEFAULT_FOULS_PER_GAME = 25.0


def _referee_perfil(cartoes_media: float, indice_cf: float | None) -> str:
    if indice_cf is not None and indice_cf >= 0.28:
        return "punitivista"
    if cartoes_media >= 5.0:
        return "punitivista"
    if cartoes_media <= 3.5:
        return "pacificador"
    return "equilibrado"


def map_referee_to_feju(referee: dict[str, Any] | None) -> FejuArbitro | None:
    if not referee:
        return None

    games = int(referee.get("games") or 0)
    name = referee.get("name") or referee.get("slug")
    if games < 3:
        return FejuArbitro(nome_arbitro=name, perfil="equilibrado")

    yellow = int(referee.get("yellowCards") or 0)
    red = int(referee.get("redCards") or 0)
    yellow_red = int(referee.get("yellowRedCards") or 0)
    cards_total = yellow + red + yellow_red
    cartoes_media = cards_total / games
    indice_cf = cartoes_media / DEFAULT_FOULS_PER_GAME

    return FejuArbitro(
        nome_arbitro=name,
        cartoes_media=round(cartoes_media, 2),
        faltas_media=None,
        indice_cartao_falta=round(indice_cf, 3),
        perfil=_referee_perfil(cartoes_media, indice_cf),
    )
