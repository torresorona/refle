"""Celery application. Scheduled connector scans and control tests land in Phase 2."""

from __future__ import annotations

from celery import Celery
from refle_core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "refle",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="refle.ping")
def ping() -> str:
    """Smoke-test task."""
    return "pong"
