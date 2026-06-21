"""AI assistant: RAG chat over the org's controls, policies, and evidence."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from refle_ai_core.embeddings import get_embedder
from refle_ai_core.gateway import AIGateway
from refle_ai_core.providers.base import Message
from refle_core.models import Embedding
from sqlalchemy import func, select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.rag import index_org_content, retrieve
from refle_api.schemas import (
    AIStatus,
    ChatRequest,
    ChatResponse,
    Citation,
    ReindexResult,
)

router = APIRouter(prefix="/ai", tags=["ai"])

SYSTEM_PROMPT = (
    "You are a SOC 2 compliance assistant for the refle platform. Answer the user's "
    "question using ONLY the numbered context sources provided. Cite sources inline "
    "like [1], [2]. If the context is insufficient, say so plainly. Be concise."
)


async def _indexed_count(session, org_id) -> int:
    return (
        await session.execute(
            select(func.count(Embedding.id)).where(Embedding.organization_id == org_id)
        )
    ).scalar_one()


@router.get("/status", response_model=AIStatus)
async def ai_status(ctx: AuthDep, session: SessionDep) -> AIStatus:
    info = AIGateway().info
    return AIStatus(
        provider=info.provider,
        model=info.model,
        sovereign=info.sovereign,
        embedding_provider=type(get_embedder()).__name__,
        indexed_chunks=await _indexed_count(session, ctx.organization.id),
    )


@router.post("/reindex", response_model=ReindexResult)
async def reindex(session: SessionDep, ctx: OwnerOrAdmin) -> ReindexResult:
    try:
        count = await index_org_content(session, ctx.organization.id, get_embedder())
    except Exception as exc:  # noqa: BLE001 - report upstream embedder failure cleanly
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"embedding provider error: {exc}",
        ) from exc
    return ReindexResult(indexed=count)


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, ctx: AuthDep, session: SessionDep) -> ChatResponse:
    org_id = ctx.organization.id
    embedder = get_embedder()

    try:
        if await _indexed_count(session, org_id) == 0:
            await index_org_content(session, org_id, embedder)
        hits = await retrieve(session, org_id, body.question, embedder, k=5)
    except Exception as exc:  # noqa: BLE001 - degrade if the embedder is unavailable
        return ChatResponse(
            answer=(
                f"The embedding provider is unavailable ({exc}). Check "
                "REFLE_AI_EMBEDDING_PROVIDER and GEMINI_API_KEY."
            ),
            citations=[],
            generated=False,
            model=AIGateway().info.model,
        )
    citations = [
        Citation(n=i + 1, source_type=h.source_type, source_id=h.source_id, title=h.title)
        for i, h in enumerate(hits)
    ]
    context = "\n".join(
        f"[{i + 1}] ({h.source_type}) {h.title}: {h.chunk_text}" for i, h in enumerate(hits)
    )

    gateway = AIGateway()
    messages = [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=f"Context:\n{context}\n\nQuestion: {body.question}"),
    ]

    generated = True
    try:
        answer = await gateway.chat(messages)
    except Exception:  # noqa: BLE001 - degrade to retrieval-only if the LLM is unavailable
        generated = False
        if citations:
            listed = "\n".join(f"[{c.n}] {c.title}" for c in citations)
            answer = (
                "AI generation is unavailable (configure GEMINI_API_KEY to enable it). "
                f"Here are the most relevant sources for your question:\n{listed}"
            )
        else:
            answer = "No indexed content yet — add controls, policies, or evidence first."

    return ChatResponse(
        answer=answer, citations=citations, generated=generated, model=gateway.info.model
    )
