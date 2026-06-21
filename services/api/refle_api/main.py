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
from refle_api.routers import (
    ai,
    auth,
    controls,
    evidence,
    health,
    integrations,
    meta,
    notifications,
    policies,
    reports,
    templates,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register built-in connectors; the enterprise package registers premium ones here too.
    from refle_ai_core.agents import register_builtin_agents
    from refle_integrations.connectors import register_builtin_connectors

    register_builtin_connectors()
    register_builtin_agents()
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
    app.include_router(auth.router)
    app.include_router(controls.router)
    app.include_router(policies.router)
    app.include_router(evidence.router)
    app.include_router(integrations.router)
    app.include_router(ai.router)
    app.include_router(notifications.router)
    app.include_router(templates.router)
    app.include_router(reports.router)
    return app


app = create_app()
