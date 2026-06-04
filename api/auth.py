"""Autenticação por API key (header X-API-Key ou Authorization: Bearer)."""
from __future__ import annotations

import secrets
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings

_PUBLIC_PREFIXES = (
    "/health/live",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def valid_api_keys() -> frozenset[str]:
    raw = settings.api_key
    if not raw or not raw.strip():
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def api_key_enabled() -> bool:
    return bool(valid_api_keys())


def extract_api_key(request: Request) -> str | None:
    header = request.headers.get("X-API-Key")
    if header and header.strip():
        return header.strip()
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        return token or None
    return None


def is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in _PUBLIC_PREFIXES)


def verify_api_key(provided: str | None, *, keys: frozenset[str] | None = None) -> bool:
    expected = keys if keys is not None else valid_api_keys()
    if not expected:
        return True
    if not provided:
        return False
    return any(secrets.compare_digest(provided, key) for key in expected)


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        keys = valid_api_keys()
        if not keys:
            return await call_next(request)

        if request.method == "OPTIONS" or is_public_path(request.url.path):
            return await call_next(request)

        if not verify_api_key(extract_api_key(request), keys=keys):
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "API key inválida ou ausente. Use o header X-API-Key ou Authorization: Bearer <key>.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)
