"""The tenant root entity."""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TimestampMixin, UUIDMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(index=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
