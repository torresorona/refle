"""Liveness and database-readiness checks."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from refle_api.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(session: SessionDep) -> dict:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
