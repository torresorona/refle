"""Framework / control skeleton.

``Framework`` and ``Control`` are the shared catalog (e.g. SOC 2 and its criteria),
seeded from ``content/``. ``OrgControl`` is a tenant's adoption + live status of a
control, which the posture dashboard aggregates. The model is deliberately
crosswalk-ready: a future ``control_mappings`` table lets one piece of evidence
satisfy controls across frameworks (e.g. ISO 27001).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class Framework(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "frameworks"

    key: Mapped[str] = mapped_column(unique=True, index=True)  # e.g. "soc2"
    name: Mapped[str]
    version: Mapped[str | None] = mapped_column(default=None)


class Control(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "controls"
    __table_args__ = (UniqueConstraint("framework_id", "code"),)

    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("frameworks.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(index=True)  # e.g. "CC6.1"
    title: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str | None] = mapped_column(default=None)  # e.g. "Logical Access"


class ControlStatus(enum.StrEnum):
    passing = "passing"
    failing = "failing"
    not_assessed = "not_assessed"


class OrgControl(UUIDMixin, TimestampMixin, TenantMixin, Base):
    """Per-organization adoption and live status of a catalog control."""

    __tablename__ = "org_controls"
    __table_args__ = (UniqueConstraint("organization_id", "control_id"),)

    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controls.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ControlStatus] = mapped_column(
        Enum(ControlStatus, name="control_status"),
        default=ControlStatus.not_assessed,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    # An org can scope a control out of its program (marked not applicable);
    # out-of-scope controls are excluded from posture and readiness gaps.
    in_scope: Mapped[bool] = mapped_column(Boolean, default=True)
