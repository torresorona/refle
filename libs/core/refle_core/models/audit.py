"""Generic human-action audit log.

Distinct from ``AiRun`` (which audits agent executions). Records who did what,
when — a baseline a compliance platform must have, and a prerequisite for any
runtime admin surface.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class AuditLog(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    action: Mapped[str] = mapped_column(String, index=True)  # e.g. "control.scope"
    target_type: Mapped[str | None] = mapped_column(String, default=None)
    target_id: Mapped[str | None] = mapped_column(String, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
