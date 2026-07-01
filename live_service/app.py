"""live_service/app.py: microsserviço FastAPI standalone para apostas in-play.

Uso:
    uvicorn live_service.app:app --port 8001 --reload

Ou via docker-compose (ver docker-compose.yml, serviço "live_service").
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import ApiKeyMiddleware, api_key_enabled
from config import settings
from live_service.dependencies import get_predictor
from live_service.router import live_router


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

_warm_lock = threading.Lock()


def _background_warm() -> None:
    """Pré-aquece o modelo WC em background thread."""
    try:
        get_predictor()
    except Exception:
        pass


@asynccontextmanager
async def _lifespan(app: FastAPI):
    t = threading.Thread(target=_background_warm, daemon=True, name="live-warm")
    t.start()
    yield
    # Cleanup: nothing to persist


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_live_app() -> FastAPI:
    app = FastAPI(
        title="Cactus Live Service",
        description="Microsserviço de apostas in-play ao vivo",
        version="1.0.0",
        lifespan=_lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins if hasattr(settings, "allowed_origins") else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth (mesma API key do serviço principal)
    if api_key_enabled():
        app.add_middleware(ApiKeyMiddleware)

    # Rotas live
    app.include_router(live_router)

    return app


app = create_live_app()


def main() -> None:
    import uvicorn
    uvicorn.run(
        "live_service.app:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.env == "development" if hasattr(settings, "env") else False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
