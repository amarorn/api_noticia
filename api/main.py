"""Bootstrap da API — apenas lifespan, middlewares e registro de routers.

Toda lógica de rotas foi movida para api/routers/*.
Estado compartilhado (predictor WC) vive em api/deps.py.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.deps as deps
from api.auth import ApiKeyMiddleware, api_key_enabled
from api.data_pulse import DataPulseMiddleware
from api.routers import basket, bets, live, news, system, user, wc


def _warm_sofascore_imports() -> None:
    try:
        import ingest.sofascore.client  # noqa: F401
        import ingest.sofascore.fept_ingest  # noqa: F401
        import ingest.sofascore.stats_ingest  # noqa: F401
    except ImportError:
        pass


def _warm_wc_models() -> None:
    _warm_sofascore_imports()
    try:
        from models.corners_predictor import CornersPredictor

        CornersPredictor()
        deps.get_wc_predictor()
        from api import wc_round_cache
        wc_round_cache.warm_from_disk()
        deps._wc_models_ready = True
    except ValueError:
        deps._wc_models_ready = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _warm_wc_models)
    yield


app = FastAPI(
    title="Bolão News API",
    description="API de contexto e previsão baseada em notícias esportivas",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Data-Pulse-At",
        "X-Articles-Silver",
        "X-Fixtures",
        "X-WC-Models-Ready",
        "X-Collections-Last-Run",
        "X-Latest-Silver-At",
    ],
)

app.add_middleware(DataPulseMiddleware, wc_models_ready=deps.is_models_ready)
app.add_middleware(ApiKeyMiddleware)

# Routers
app.include_router(system.router)
app.include_router(news.router)
app.include_router(wc.router)
app.include_router(live.router)
app.include_router(bets.router)
app.include_router(user.router)
app.include_router(basket.router)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title, version=app.version,
        description=app.description, routes=app.routes,
    )
    if api_key_enabled():
        schema.setdefault("components", {})["securitySchemes"] = {
            "ApiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            "BearerAuth": {"type": "http", "scheme": "bearer"},
        }
        schema["security"] = [{"ApiKeyHeader": []}, {"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi
