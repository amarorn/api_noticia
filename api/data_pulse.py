"""Pulso do datalake — snapshot compartilhado e headers em cada resposta HTTP."""
from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from api.lake_cache import get_lake_counts
from config import settings
from ingest.meta import collection_stats

_SKIP_PREFIXES = ("/health/live", "/docs", "/redoc", "/openapi.json")
_META_TTL_SECONDS = 15.0

_meta_cache: dict[str, Any] = {"at": 0.0, "collections": None, "latest_silver_at": None}
_last_snapshot: dict[str, Any] | None = None


def _cached_collections() -> dict:
    now = time.monotonic()
    if now - float(_meta_cache["at"]) < _META_TTL_SECONDS and _meta_cache["collections"] is not None:
        return _meta_cache["collections"]
    stats = collection_stats()
    _meta_cache["collections"] = stats
    _meta_cache["at"] = now
    return stats


def _cached_latest_silver_at() -> str | None:
    now = time.monotonic()
    if now - float(_meta_cache["at"]) < _META_TTL_SECONDS and _meta_cache.get("latest_silver_at") is not None:
        return _meta_cache["latest_silver_at"]

    silver_root = settings.lake_root / "silver"
    latest_at: str | None = None
    if silver_root.is_dir():
        parquets = list(silver_root.rglob("*.parquet"))
        if parquets:
            latest = max(parquets, key=lambda p: p.stat().st_mtime)
            latest_at = datetime.fromtimestamp(latest.stat().st_mtime, tz=UTC).isoformat()

    _meta_cache["latest_silver_at"] = latest_at
    _meta_cache["at"] = now
    return latest_at


def invalidate_pulse_meta_cache() -> None:
    _meta_cache["at"] = 0.0
    _meta_cache["collections"] = None
    _meta_cache["latest_silver_at"] = None


def build_pulse_snapshot(
    *,
    wc_models_ready: bool,
    force_lake_counts: bool = False,
) -> dict[str, Any]:
    global _last_snapshot
    articles_silver, fixtures = get_lake_counts(force=force_lake_counts)
    stats = _cached_collections()
    snapshot = {
        "status": "ok",
        "pulse_at": datetime.now(UTC).isoformat(),
        "lake_root": str(settings.lake_root),
        "articles_silver": articles_silver,
        "fixtures": fixtures,
        "latest_silver_at": _cached_latest_silver_at(),
        "collections": stats,
        "wc_models_ready": wc_models_ready,
        "actions": {
            "sync_news": {"method": "POST", "path": "/news/sync"},
            "feed": {"method": "GET", "path": "/news/all"},
        },
    }
    _last_snapshot = snapshot
    return snapshot


def get_last_pulse_snapshot() -> dict[str, Any] | None:
    return _last_snapshot


def pulse_response_headers(snapshot: dict[str, Any]) -> dict[str, str]:
    collections = snapshot.get("collections") or {}
    last_run = collections.get("last_run")
    return {
        "X-Data-Pulse-At": str(snapshot["pulse_at"]),
        "X-Articles-Silver": str(snapshot["articles_silver"]),
        "X-Fixtures": str(snapshot["fixtures"]),
        "X-WC-Models-Ready": "true" if snapshot.get("wc_models_ready") else "false",
        "X-Collections-Last-Run": last_run if last_run else "",
        "X-Latest-Silver-At": snapshot.get("latest_silver_at") or "",
    }


class DataPulseMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, wc_models_ready: Callable[[], bool]) -> None:
        super().__init__(app)
        self._wc_models_ready = wc_models_ready

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _SKIP_PREFIXES):
            return await call_next(request)

        import asyncio

        snapshot = await asyncio.to_thread(
            build_pulse_snapshot,
            wc_models_ready=self._wc_models_ready(),
        )
        request.state.data_pulse = snapshot

        response = await call_next(request)
        for key, value in pulse_response_headers(snapshot).items():
            response.headers[key] = value
        return response
