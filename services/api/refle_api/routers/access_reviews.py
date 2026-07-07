"""Access reviews: periodic attestation of who has access to what (CC6)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from refle_core.models import (
    AccessDecision,
    AccessReview,
    AccessReviewItem,
    AccessReviewStatus,
    Person,
    RemediationStatus,
    RemediationTask,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_api.deps import AuthDep, Members, SessionDep
from refle_api.schemas import (
    AccessDecisionInput,
    AccessReviewCreate,
    AccessReviewDetail,
    AccessReviewItemOut,
    AccessReviewOut,
)

router = APIRouter(prefix="/access-reviews", tags=["access-reviews"])


async def _detail(session: AsyncSession, review: AccessReview) -> AccessReviewDetail:
    items = (
        (
            await session.execute(
                select(AccessReviewItem)
                .where(AccessReviewItem.review_id == review.id)
                .order_by(AccessReviewItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    base = AccessReviewOut.model_validate(review)
    return AccessReviewDetail(
        **base.model_dump(), items=[AccessReviewItemOut.model_validate(i) for i in items]
    )


async def _get_review(
    session: AsyncSession, review_id: uuid.UUID, org_id: uuid.UUID
) -> AccessReview:
    review = (
        await session.execute(
            select(AccessReview).where(
                AccessReview.id == review_id, AccessReview.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="review not found")
    return review


async def _validate_people(
    session: AsyncSession, person_ids: set[uuid.UUID], org_id: uuid.UUID
) -> None:
    if not person_ids:
        return
    found = set(
        (
            await session.execute(
                select(Person.id).where(
                    Person.organization_id == org_id,
                    Person.id.in_(person_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    missing = person_ids - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"person not found: {sorted(str(p) for p in missing)}",
        )


@router.post("", response_model=AccessReviewDetail, status_code=status.HTTP_201_CREATED)
async def create_review(
    body: AccessReviewCreate, session: SessionDep, ctx: Members
) -> AccessReviewDetail:
    await _validate_people(
        session,
        {item.person_id for item in body.items if item.person_id is not None},
        ctx.organization.id,
    )
    review = AccessReview(
        organization_id=ctx.organization.id, name=body.name, due_at=body.due_at
    )
    session.add(review)
    await session.flush()
    for it in body.items:
        session.add(
            AccessReviewItem(
                organization_id=ctx.organization.id,
                review_id=review.id,
                person_id=it.person_id,
                system=it.system,
                access_detail=it.access_detail,
            )
        )
    await session.commit()
    await session.refresh(review)
    return await _detail(session, review)


@router.get("", response_model=list[AccessReviewOut])
async def list_reviews(ctx: AuthDep, session: SessionDep) -> list[AccessReviewOut]:
    rows = (
        (
            await session.execute(
                select(AccessReview)
                .where(AccessReview.organization_id == ctx.organization.id)
                .order_by(AccessReview.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [AccessReviewOut.model_validate(r) for r in rows]


@router.get("/{review_id}", response_model=AccessReviewDetail)
async def get_review(
    review_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> AccessReviewDetail:
    return await _detail(session, await _get_review(session, review_id, ctx.organization.id))


@router.post("/items/{item_id}/decision", response_model=AccessReviewItemOut)
async def record_decision(
    item_id: uuid.UUID, body: AccessDecisionInput, session: SessionDep, ctx: Members
) -> AccessReviewItemOut:
    item = (
        await session.execute(
            select(AccessReviewItem).where(
                AccessReviewItem.id == item_id,
                AccessReviewItem.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")

    item.decision = body.decision
    item.reviewed_by_id = ctx.user.id
    item.reviewed_at = datetime.now(UTC)

    # A revoke decision opens a remediation task (evidence the action was tracked).
    if body.decision == AccessDecision.revoke:
        session.add(
            RemediationTask(
                organization_id=ctx.organization.id,
                title=f"Revoke access: {item.system}",
                detail=item.access_detail or "Access flagged for revocation in an access review.",
                status=RemediationStatus.open,
                source="access_review",
            )
        )

    await session.commit()
    await session.refresh(item)
    return AccessReviewItemOut.model_validate(item)


@router.post("/{review_id}/complete", response_model=AccessReviewDetail)
async def complete_review(
    review_id: uuid.UUID, session: SessionDep, ctx: Members
) -> AccessReviewDetail:
    review = await _get_review(session, review_id, ctx.organization.id)
    review.status = AccessReviewStatus.completed
    review.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(review)
    return await _detail(session, review)
