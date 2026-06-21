"""Read-only access to the human-action audit log (owner/admin)."""

from __future__ import annotations

from fastapi import APIRouter
from refle_core.models import AuditLog
from sqlalchemy import select

from refle_api.deps import OwnerOrAdmin, SessionDep
from refle_api.schemas import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(ctx: OwnerOrAdmin, session: SessionDep) -> list[AuditLogOut]:
    rows = (
        (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.organization_id == ctx.organization.id)
                .order_by(AuditLog.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [AuditLogOut.model_validate(r) for r in rows]
