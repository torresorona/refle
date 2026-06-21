"""Vector embeddings of org content for retrieval-augmented chat."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from refle_core.models.base import Base, TenantMixin, TimestampMixin, UUIDMixin

EMBEDDING_DIM = 768


class Embedding(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "embeddings"
    __table_args__ = (Index("ix_embeddings_org_source", "organization_id", "source_type"),)

    source_type: Mapped[str]  # "control" | "policy" | "evidence"
    source_id: Mapped[str]  # control code or row id
    title: Mapped[str]
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
