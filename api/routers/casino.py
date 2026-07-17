"""Rotas de catálogo casino Superbet (metadados públicos — apostas na Evolution)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from api.schemas import (
    BacboIngestRequest,
    BacboIngestResponse,
    BacboRoundsResponse,
    CasinoCatalogResponse,
    CasinoGameResponse,
)
from ingest.superbet.bacbo_parser import extract_table_id_from_ws_url, parse_bacbo_ws_batch
from ingest.superbet.bacbo_store import append_bacbo_rounds, list_bacbo_rounds
from ingest.superbet.gaming import (
    CURATED_CASINO_SEO_IDS,
    SuperbetGamingClient,
    SuperbetGamingClientError,
)

router = APIRouter(prefix="/casino", tags=["casino"])


def _to_response(game) -> CasinoGameResponse:
    return CasinoGameResponse(**game.to_dict())


@router.get("/games", response_model=CasinoCatalogResponse)
async def casino_catalog():
    """Lista jogos casino curados (API pública Superbet Gaming)."""
    client = SuperbetGamingClient()
    try:
        games = await asyncio.to_thread(client.fetch_curated_catalog)
    except SuperbetGamingClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return CasinoCatalogResponse(
        count=len(games),
        seo_ids=list(CURATED_CASINO_SEO_IDS),
        games=[_to_response(g) for g in games],
        captured_at=datetime.now(UTC).isoformat(),
        betting_note=(
            "Apostas de casino ocorrem via WebSocket Evolution após login na Superbet; "
            "não há endpoint REST de aposta equivalente ao bilhete esportivo."
        ),
    )


@router.get("/games/{seo_id}", response_model=CasinoGameResponse)
async def casino_game(seo_id: str):
    """Metadados de um jogo casino pelo seo_id (ex.: 379099 = Bac Bo Superbet)."""
    client = SuperbetGamingClient()
    try:
        game = await asyncio.to_thread(client.fetch_game_by_seo_id, seo_id)
    except SuperbetGamingClientError as exc:
        status = 404 if "não encontrado" in str(exc).lower() else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    return _to_response(game)


@router.post("/bacbo/ingest", response_model=BacboIngestResponse)
async def casino_bacbo_ingest(body: BacboIngestRequest):
    """Ingestão de mensagens WS Bac Bo (extensão Bolão AI)."""
    table_id = body.table_id
    if not table_id and body.ws_url:
        table_id = extract_table_id_from_ws_url(body.ws_url) or ""
    if not table_id:
        table_id = "unknown"

    records = parse_bacbo_ws_batch(body.messages, table_id=table_id, ws_url=body.ws_url or "")
    result = await asyncio.to_thread(
        append_bacbo_rounds,
        records,
        raw_messages=body.messages,
        ws_url=body.ws_url,
    )
    debug = result.get("debug") or {}
    msg_types = debug.get("message_types") or {}
    return BacboIngestResponse(
        inserted=result["inserted"],
        parsed=len(records),
        table_id=table_id,
        updated_at=result["store"].get("updated_at"),
        message_types_seen=dict(list(msg_types.items())[-8:]) if msg_types else None,
    )


@router.get("/bacbo/rounds", response_model=BacboRoundsResponse)
async def casino_bacbo_rounds(
    table_id: str | None = None,
    limit: int = 50,
):
    """Últimas rodadas Bac Bo capturadas (somente leitura)."""
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    payload = await asyncio.to_thread(list_bacbo_rounds, table_id=table_id, limit=limit)
    if table_id:
        return BacboRoundsResponse(**payload)
    return BacboRoundsResponse(
        table_id=None,
        count=payload.get("count", 0),
        stats={},
        rounds=[],
        updated_at=payload.get("updated_at"),
        tables=payload.get("tables"),
    )
