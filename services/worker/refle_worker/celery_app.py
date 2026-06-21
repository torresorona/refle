"""Celery application: scheduled connector syncs and control tests."""

from __future__ import annotations

import asyncio

from celery import Celery
from refle_ai_core.agents import register_builtin_agents
from refle_core.config import get_settings
from refle_integrations.connectors import register_builtin_connectors

settings = get_settings()
register_builtin_connectors()
register_builtin_agents()

celery_app = Celery(
    "refle",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-connections-hourly": {
            "task": "refle.sync_all_connections",
            "schedule": 3600.0,
        },
    },
)


@celery_app.task(name="refle.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="refle.sync_all_connections")
def sync_all_connections() -> dict:
    """Run every connection through the engine (collect -> test -> posture)."""
    return asyncio.run(_sync_all())


async def _sync_all() -> dict:
    from datetime import UTC, datetime

    from refle_api.notify import dispatch_notifications
    from refle_core.db import get_sessionmaker
    from refle_core.models import Connection
    from refle_integrations.engine import is_due, run_connection
    from sqlalchemy import select

    now = datetime.now(UTC)
    synced = 0
    skipped = 0
    failed = 0
    async with get_sessionmaker()() as session:
        connections = (await session.execute(select(Connection))).scalars().all()
        for connection in connections:
            if not is_due(connection, now):
                skipped += 1
                continue
            outcome = await run_connection(session, connection)
            if outcome.notifications:
                await dispatch_notifications(session, outcome.notifications)
            synced += 1
            if not outcome.ok:
                failed += 1
    return {"connections": synced, "skipped": skipped, "errored": failed}
