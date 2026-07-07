"""AI assistant: RAG chat over the org's controls, policies, and evidence."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from refle_ai_core.embeddings import get_embedder
from refle_ai_core.gateway import AIGateway
from refle_ai_core.providers.base import Message
from refle_core.ai_runs import record_agent_run
from refle_core.models import (
    Control,
    Embedding,
    Evidence,
    OrgControl,
    Policy,
    PolicyTemplate,
    PolicyVersion,
    Role,
)
from refle_core.models.policy import PolicyVersionStatus
from refle_extensions.registry import agent_registry
from sqlalchemy import func, select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.rag import index_org_content, retrieve
from refle_api.routers.policies import _policy_detail, _unique_slug
from refle_api.schemas import (
    AIStatus,
    ChatRequest,
    ChatResponse,
    Citation,
    DraftPolicyRequest,
    PolicyDetail,
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
    gateway = AIGateway()
    info = gateway.info
    return AIStatus(
        provider=info.provider,
        model=info.model,
        agent_model=gateway.settings.agent_model,
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
        indexed_count = await _indexed_count(session, org_id)
        if indexed_count == 0 and ctx.role != Role.auditor:
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


@router.post(
    "/agents/draft-policy", response_model=PolicyDetail, status_code=status.HTTP_201_CREATED
)
async def draft_policy(
    body: DraftPolicyRequest, ctx: OwnerOrAdmin, session: SessionDep
) -> PolicyDetail:
    org_id = ctx.organization.id
    try:
        agent = agent_registry.get("draft-policy")
    except KeyError as e:
        raise HTTPException(status_code=500, detail="draft-policy agent not found") from e

    # Gather context
    controls = (
        (
            await session.execute(
                select(Control)
                .join(OrgControl, OrgControl.control_id == Control.id)
                .where(OrgControl.organization_id == org_id)
            )
        )
        .scalars()
        .all()
    )
    context = {
        "controls": [
            {"code": c.code, "title": c.title, "description": c.description} for c in controls
        ]
    }

    if body.template_id:
        tpl = (
            await session.execute(
                select(PolicyTemplate).where(
                    PolicyTemplate.id == body.template_id,
                    (PolicyTemplate.organization_id.is_(None))
                    | (PolicyTemplate.organization_id == org_id),
                )
            )
        ).scalar_one_or_none()
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        context["template_body"] = tpl.body
    elif not body.evidence_id:
        # Generate from scratch using the gold standard builtin template
        from refle_core.models import TemplateType

        tpl = (
            await session.execute(
                select(PolicyTemplate).where(PolicyTemplate.type == TemplateType.builtin).limit(1)
            )
        ).scalar_one_or_none()
        if tpl:
            context["template_body"] = tpl.body

    if body.evidence_id:
        from fastapi.concurrency import run_in_threadpool
        from refle_ai_core.providers.base import Attachment

        from refle_api import storage

        ev = (
            await session.execute(
                select(Evidence).where(
                    Evidence.id == body.evidence_id, Evidence.organization_id == org_id
                )
            )
        ).scalar_one_or_none()
        if not ev:
            raise HTTPException(status_code=404, detail="Evidence not found")

        raw_bytes = await run_in_threadpool(storage.get_object, ev.object_key)
        context["attachment"] = Attachment(
            mime_type=ev.content_type or "application/octet-stream", data=raw_bytes
        )

    # Run the agent and record an AiRun audit row (failed runs are persisted too).
    params = {"name": body.name, "instructions": body.instructions}
    try:
        result, _ = await record_agent_run(
            session,
            organization_id=org_id,
            agent=agent,
            context=context,
            params=params,
        )
    except Exception as exc:  # noqa: BLE001 - run already recorded as failed; surface a 500
        raise HTTPException(status_code=500, detail=f"Agent failed: {exc}") from exc

    # Create policy
    policy = Policy(
        organization_id=org_id,
        name=body.name,
        slug=await _unique_slug(session, org_id, body.name, None),
        description=body.instructions,
    )
    session.add(policy)
    await session.flush()

    session.add(
        PolicyVersion(
            policy_id=policy.id,
            version=1,
            body=result.output,
            created_by_id=ctx.user.id,
            status=PolicyVersionStatus.draft,
            source_template_id=body.template_id,
            source_evidence_id=body.evidence_id,
        )
    )
    await session.commit()
    return await _policy_detail(session, policy, ctx.user.id)
