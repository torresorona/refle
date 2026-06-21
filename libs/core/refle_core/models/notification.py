import enum
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class NotificationLevel(str, enum.Enum):
    info = "info"
    warning = "warning"


class Notification(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "notifications"

    type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    level: Mapped[NotificationLevel] = mapped_column(
        SQLEnum(NotificationLevel), default=NotificationLevel.info
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class NotificationSetting(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "notification_settings"

    slack_webhook_url: Mapped[str | None] = mapped_column(String, default=None)
    email_to: Mapped[str | None] = mapped_column(String, default=None)
    channels: Mapped[str] = mapped_column(String, default="slack,email")
