import enum
from typing import Any

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin


class AiRunStatus(str, enum.Enum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class AiRun(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "ai_runs"

    agent_key: Mapped[str]
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    output: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[AiRunStatus] = mapped_column(SQLEnum(AiRunStatus), default=AiRunStatus.running)
    model: Mapped[str]
    error: Mapped[str | None] = mapped_column(Text, default=None)
