from __future__ import annotations

from typing import Any

from ingest.sofascore.kxl_sofascore_ingest import build_kxl_sofascore_payload
from pipelines.wc_kxl_fept import fept_players_for_side
from schemas.national_teams import normalize_national_team
from schemas.wc_kxl_dynamic import FeptJogador, WcKxlMatchInput, WcKxlPartida


def _serialize_fept_player(player: FeptJogador) -> dict[str, Any]:
    return {
        "name": player.nome,
        "position": player.posicao,
        "line": player.linha,
        "sofascore_rating": player.nota_sofascore,
    }


def _merge_meta(result, *, auto_merged: bool, note: str | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "source": "sofascore",
        "event_id": result.event_id,
        "ratings_found": result.ratings_found,
        "ratings_missing": result.ratings_missing,
        "esquema_mandante": result.fept.esquema_mandante,
        "esquema_visitante": result.fept.esquema_visitante,
        "home_players": [
            _serialize_fept_player(player) for player in fept_players_for_side(result.fept, True)
        ],
        "away_players": [
            _serialize_fept_player(player) for player in fept_players_for_side(result.fept, False)
        ],
        "absences_home": result.absences_home,
        "absences_away": result.absences_away,
        "auto_merged": auto_merged,
    }
    if result.feju:
        meta["referee"] = result.feju.nome_arbitro
        meta["referee_profile"] = result.feju.perfil
        meta["referee_cards_per_game"] = result.feju.cartoes_media
    if note:
        meta["note"] = note
    return meta


def merge_sofascore_fept(
    *,
    kxl_match: WcKxlMatchInput | None,
    sofascore_event_id: int | None,
    home_team: str,
    away_team: str,
) -> tuple[WcKxlMatchInput | None, dict[str, Any] | None]:
    if sofascore_event_id is None:
        return kxl_match, None

    home = normalize_national_team(home_team)
    away = normalize_national_team(away_team)
    result = build_kxl_sofascore_payload(
        home_team=home,
        away_team=away,
        event_id=sofascore_event_id,
    )

    updates: dict[str, Any] = {}
    notes: list[str] = []
    auto = True

    if kxl_match is None:
        return (
            WcKxlMatchInput(
                partida=WcKxlPartida(mandante=home, visitante=away),
                fept=result.fept,
                fede=result.fede,
                feju=result.feju,
            ),
            _merge_meta(result, auto_merged=True),
        )

    if kxl_match.fept is None:
        updates["fept"] = result.fept
    else:
        auto = False
        notes.append("FEPT manual preservado")

    if kxl_match.fede is None and (
        result.absences_home > 0 or result.absences_away > 0
    ):
        updates["fede"] = result.fede
    elif kxl_match.fede is not None:
        auto = False
        notes.append("FEDE manual preservado")

    if kxl_match.feju is None and result.feju is not None:
        updates["feju"] = result.feju
    elif kxl_match.feju is not None:
        auto = False
        notes.append("FEJU manual preservado")

    note = "; ".join(notes) if notes else None
    if not updates:
        return kxl_match, _merge_meta(result, auto_merged=False, note=note)

    return kxl_match.model_copy(update=updates), _merge_meta(
        result,
        auto_merged=auto and not notes,
        note=note,
    )
