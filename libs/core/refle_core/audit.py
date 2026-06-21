"""Helper to record a human-action ``AuditLog`` entry.

Adds the row to the caller's session (the caller commits), so it participates in
the same transaction as the change it describes.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from refle_core.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    summary: str | None = None,
) -> None:
    session.add(
        AuditLog(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            summary=summary,
        )
    )
