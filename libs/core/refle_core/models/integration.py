"""Integration connections, automated test-result history, and remediation tasks."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class ConnectionStatus(enum.StrEnum):
    never_synced = "never_synced"
    connected = "connected"
    error = "error"


class Connection(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "connections"

    provider: Mapped[str] = mapped_column(index=True)  # e.g. "aws", "github", "okta"
    label: Mapped[str]
    encrypted_credentials: Mapped[str] = mapped_column(Text)
    status: Mapped[ConnectionStatus] = mapped_column(
        SAEnum(ConnectionStatus, name="connection_status"),
        default=ConnectionStatus.never_synced,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class ControlTestResult(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Append-only history of automated control-test runs (drives posture over time)."""

    __tablename__ = "control_test_results"

    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), index=True, default=None
    )
    test_key: Mapped[str] = mapped_column(index=True)  # e.g. "aws.iam.mfa_enabled"
    control_code: Mapped[str] = mapped_column(index=True)  # e.g. "CC6.1"
    passed: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(Text, default=None)


class RemediationStatus(enum.StrEnum):
    open = "open"
    resolved = "resolved"


class RemediationTask(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "remediation_tasks"

    title: Mapped[str]
    control_code: Mapped[str | None] = mapped_column(index=True, default=None)
    detail: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[RemediationStatus] = mapped_column(
        SAEnum(RemediationStatus, name="remediation_status"),
        default=RemediationStatus.open,
    )
    source: Mapped[str] = mapped_column(default="automated")
