"""People domain: employees, on/offboarding checklists, security training, and
access reviews. Feeds the SOC 2 CC1 (personnel) and CC6 (access) criteria.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class PersonStatus(enum.StrEnum):
    active = "active"
    terminated = "terminated"


class ChecklistKind(enum.StrEnum):
    onboarding = "onboarding"
    offboarding = "offboarding"


class AccessReviewStatus(enum.StrEnum):
    open = "open"
    completed = "completed"


class AccessDecision(enum.StrEnum):
    pending = "pending"
    keep = "keep"
    revoke = "revoke"


class Person(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "people"

    full_name: Mapped[str]
    email: Mapped[str] = mapped_column(index=True)
    title: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[PersonStatus] = mapped_column(
        SAEnum(PersonStatus, name="person_status"), default=PersonStatus.active
    )
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), default=None
    )
    # Optional link to a platform login (a Person need not be a User).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class ChecklistItem(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "checklist_items"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ChecklistKind] = mapped_column(SAEnum(ChecklistKind, name="checklist_kind"))
    label: Mapped[str]
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    done_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )


class TrainingRecord(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "training_records"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    course: Mapped[str]
    completed_at: Mapped[date | None] = mapped_column(Date, default=None)
    expires_at: Mapped[date | None] = mapped_column(Date, default=None)


class AccessReview(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "access_reviews"

    name: Mapped[str]
    status: Mapped[AccessReviewStatus] = mapped_column(
        SAEnum(AccessReviewStatus, name="access_review_status"),
        default=AccessReviewStatus.open,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class AccessReviewItem(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "access_review_items"

    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("access_reviews.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), default=None
    )
    system: Mapped[str]  # e.g. "okta", "github", or free text
    access_detail: Mapped[str | None] = mapped_column(Text, default=None)
    decision: Mapped[AccessDecision] = mapped_column(
        SAEnum(AccessDecision, name="access_decision"), default=AccessDecision.pending
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# Default checklist contents (org-customizable templates are a follow-up).
DEFAULT_ONBOARDING = [
    "Account provisioned with least privilege",
    "MFA enabled",
    "Security awareness training assigned",
    "Acceptable use & security policies accepted",
    "Equipment issued and encrypted",
]
DEFAULT_OFFBOARDING = [
    "All system access revoked",
    "MFA / SSO sessions terminated",
    "Equipment returned",
    "Credentials and API keys rotated",
    "Email forwarded / archived",
]
