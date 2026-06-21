"""Policies with versioning and per-employee acceptance."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class PolicyVersionStatus(enum.StrEnum):
    draft = "draft"
    published = "published"


class TemplateType(enum.StrEnum):
    builtin = "builtin"
    custom = "custom"


class PolicyTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_templates"

    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text, default=None)
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[TemplateType] = mapped_column(SQLEnum(TemplateType), default=TemplateType.custom)
    # organization_id is nullable: None means it's a globally available built-in template.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, default=None
    )


class Policy(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("organization_id", "slug"),)

    name: Mapped[str]
    slug: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)


class PolicyVersion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version"),)

    policy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[PolicyVersionStatus] = mapped_column(
        SQLEnum(PolicyVersionStatus), default=PolicyVersionStatus.published
    )
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("policy_templates.id", ondelete="SET NULL"), default=None
    )
    source_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id", ondelete="SET NULL"), default=None
    )


class PolicyAcceptance(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "policy_acceptances"
    __table_args__ = (UniqueConstraint("policy_version_id", "user_id"),)

    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
