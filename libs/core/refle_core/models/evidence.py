"""Evidence artifacts and their mapping to org controls."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, ForeignKey, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class EvidenceSource(enum.StrEnum):
    manual = "manual"
    integration = "integration"


class Evidence(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "evidence"

    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[EvidenceSource] = mapped_column(
        SAEnum(EvidenceSource, name="evidence_source"),
        default=EvidenceSource.manual,
    )
    object_key: Mapped[str]  # key in the object store
    filename: Mapped[str]
    content_type: Mapped[str | None] = mapped_column(default=None)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    content_sha256: Mapped[str | None] = mapped_column(default=None)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class EvidenceControl(UUIDMixin, TimestampMixin, Base):
    """Links a piece of evidence to an org control it helps satisfy."""

    __tablename__ = "evidence_controls"
    __table_args__ = (UniqueConstraint("evidence_id", "org_control_id"),)

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence.id", ondelete="CASCADE"), index=True
    )
    org_control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org_controls.id", ondelete="CASCADE"), index=True
    )
