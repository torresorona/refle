"""Owner-approved account onboarding requests."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from refle_core.models.user import Role


class AccessRequestStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AccessRequest(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "access_requests"
    __table_args__ = (UniqueConstraint("organization_id", "email", "status"),)

    email: Mapped[str] = mapped_column(index=True)
    full_name: Mapped[str | None] = mapped_column(default=None)
    hashed_password: Mapped[str] = mapped_column()
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.member)
    status: Mapped[AccessRequestStatus] = mapped_column(
        Enum(AccessRequestStatus, name="access_request_status"),
        default=AccessRequestStatus.pending,
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
