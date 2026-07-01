"""Rotas de sistema: health, config, sportradar, data pulse."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

import api.deps as deps
from api.lake_cache import get_lake_counts
from config import settings
from ingest.meta import collection_stats

router = APIRouter()


@router.get("/")
def root():
    from api.auth import api_key_enabled

    return {
        "name": "api-noticia",
        "status": "running",
        "auth_required": api_key_enabled(),
        "docs": "/docs",
        "health": "/health",
        "data_pulse": "/data/pulse",
    }


@router.get("/health/live")
def health_live():
    return {"status": "ok"}


@router.get("/health")
async def health():
    stats = collection_stats()
    articles_silver, fixtures = await asyncio.to_thread(get_lake_counts)
    return {
        "status": "ok",
        "lake_root": str(settings.lake_root),
        "articles_silver": articles_silver,
        "fixtures": fixtures,
        "collections": stats,
        "wc_models_ready": deps.is_models_ready(),
        "wc_artifact": deps.get_artifact_meta() if deps.is_models_ready() else None,
    }


@router.get("/data/pulse")
async def data_pulse():
    from api.data_pulse import build_pulse_snapshot

    return await asyncio.to_thread(
        build_pulse_snapshot,
        wc_models_ready=deps.is_models_ready(),
        force_lake_counts=True,
    )


@router.get("/config/sportradar")
def config_sportradar():
    from api.sportradar_embed import sportradar_public_config

    payload = sportradar_public_config()
    return {
        "widget": payload["widget"],
        "language": payload["language"],
        "embed_available": payload["embed_available"],
        "client_id_configured": payload["client_id"] is not None,
    }


@router.get("/sportradar/lmt/{betradar_id}", response_class=HTMLResponse)
def sportradar_lmt_embed(betradar_id: str):
    from api.sportradar_embed import lmt_embed_response

    return lmt_embed_response(betradar_id=betradar_id)
