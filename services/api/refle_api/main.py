"""FastAPI application factory.

The factory is the wiring point for extension modules: when the private
``refle-enterprise`` package is installed it can register routers, connectors,
agents, and a license provider here without core changing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from refle_core.config import get_settings

from refle_api import __version__
from refle_api.routers import health, meta


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hook for loading optional enterprise extensions / warming resources.
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="refle API", version=__version__, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(meta.router)
    return app


app = create_app()
