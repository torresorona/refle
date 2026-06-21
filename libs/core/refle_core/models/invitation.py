"""Organization invitations — the core B2B onboarding primitive."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin
from refle_core.models.user import Role


class InvitationStatus(enum.StrEnum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"


class Invitation(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "invitations"
    # One outstanding invite per email per org.
    __table_args__ = (UniqueConstraint("organization_id", "email"),)

    email: Mapped[str] = mapped_column(index=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), default=Role.member)
    token: Mapped[str] = mapped_column(unique=True, index=True)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status"),
        default=InvitationStatus.pending,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
