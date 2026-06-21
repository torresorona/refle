"""Retrieval-augmented generation: index org content and retrieve relevant chunks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from refle_ai_core.embeddings import Embedder
from refle_core.models import (
    Control,
    Embedding,
    Evidence,
    Framework,
    Policy,
    PolicyVersion,
)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class Retrieved:
    source_type: str
    source_id: str
    title: str
    chunk_text: str
    distance: float


async def _gather_chunks(
    session: AsyncSession, org_id: uuid.UUID
) -> list[tuple[str, str, str, str]]:
    """Return (source_type, source_id, title, text) tuples to embed."""
    chunks: list[tuple[str, str, str, str]] = []

    controls = (
        (
            await session.execute(
                select(Control).join(Framework, Control.framework_id == Framework.id)
            )
        )
        .scalars()
        .all()
    )
    for c in controls:
        text = f"{c.code} {c.title}. {c.description or ''} Category: {c.category or ''}"
        chunks.append(("control", c.code, f"{c.code} — {c.title}", text))

    policies = (
        (await session.execute(select(Policy).where(Policy.organization_id == org_id)))
        .scalars()
        .all()
    )
    for p in policies:
        latest = (
            (
                await session.execute(
                    select(PolicyVersion)
                    .where(PolicyVersion.policy_id == p.id)
                    .order_by(PolicyVersion.version.desc())
                )
            )
            .scalars()
            .first()
        )
        body = latest.body if latest else ""
        chunks.append(("policy", str(p.id), p.name, f"{p.name}. {p.description or ''} {body}"))

    evidence = (
        (await session.execute(select(Evidence).where(Evidence.organization_id == org_id)))
        .scalars()
        .all()
    )
    for ev in evidence:
        chunks.append(("evidence", str(ev.id), ev.name, f"{ev.name}. {ev.description or ''}"))

    return chunks


async def index_org_content(session: AsyncSession, org_id: uuid.UUID, embedder: Embedder) -> int:
    """Rebuild the org's embedding index. Returns the number of chunks indexed."""
    chunks = await _gather_chunks(session, org_id)
    await session.execute(delete(Embedding).where(Embedding.organization_id == org_id))
    if not chunks:
        await session.commit()
        return 0

    vectors = embedder.embed([c[3] for c in chunks])
    for (source_type, source_id, title, text), vector in zip(chunks, vectors, strict=True):
        session.add(
            Embedding(
                organization_id=org_id,
                source_type=source_type,
                source_id=source_id,
                title=title,
                chunk_text=text,
                embedding=vector,
            )
        )
    await session.commit()
    return len(chunks)


async def retrieve(
    session: AsyncSession,
    org_id: uuid.UUID,
    query: str,
    embedder: Embedder,
    k: int = 5,
) -> list[Retrieved]:
    query_vec = embedder.embed([query])[0]
    distance = Embedding.embedding.cosine_distance(query_vec)
    rows = (
        await session.execute(
            select(Embedding, distance.label("distance"))
            .where(Embedding.organization_id == org_id)
            .order_by(distance)
            .limit(k)
        )
    ).all()
    return [Retrieved(e.source_type, e.source_id, e.title, e.chunk_text, float(d)) for e, d in rows]
