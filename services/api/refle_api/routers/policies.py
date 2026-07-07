"""Policy management: versioning and per-employee acceptance."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from refle_core.audit import record_audit
from refle_core.models import Policy, PolicyAcceptance, PolicyVersion
from refle_core.models.policy import PolicyVersionStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_api.deps import AuthDep, Members, OwnerOrAdmin, SessionDep
from refle_api.schemas import (
    AcceptanceOut,
    PolicyCreate,
    PolicyDetail,
    PolicyOut,
    PolicyVersionCreate,
    PolicyVersionOut,
    PolicyVersionUpdate,
)
from refle_api.services import slugify

router = APIRouter(prefix="/policies", tags=["policies"])


async def _unique_slug(
    session: AsyncSession, org_id: uuid.UUID, name: str, provided: str | None
) -> str:
    base = slugify(provided or name)
    candidate, n = base, 2
    while (
        await session.execute(
            select(Policy.id).where(Policy.organization_id == org_id, Policy.slug == candidate)
        )
    ).first() is not None:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


async def _latest_version(session: AsyncSession, policy_id: uuid.UUID) -> PolicyVersion | None:
    return (
        (
            await session.execute(
                select(PolicyVersion)
                .where(PolicyVersion.policy_id == policy_id)
                .order_by(PolicyVersion.version.desc())
            )
        )
        .scalars()
        .first()
    )


async def _latest_published_version(
    session: AsyncSession, policy_id: uuid.UUID
) -> PolicyVersion | None:
    return (
        (
            await session.execute(
                select(PolicyVersion)
                .where(
                    PolicyVersion.policy_id == policy_id,
                    PolicyVersion.status == PolicyVersionStatus.published,
                )
                .order_by(PolicyVersion.version.desc())
            )
        )
        .scalars()
        .first()
    )


async def _policy_out(session: AsyncSession, policy: Policy, user_id: uuid.UUID) -> PolicyOut:
    latest_published = await _latest_published_version(session, policy.id)
    accepted_count = 0
    accepted_by_me = False
    if latest_published is not None:
        accepted_count = (
            await session.execute(
                select(func.count(PolicyAcceptance.id)).where(
                    PolicyAcceptance.policy_version_id == latest_published.id
                )
            )
        ).scalar_one()
        accepted_by_me = (
            await session.execute(
                select(PolicyAcceptance.id).where(
                    PolicyAcceptance.policy_version_id == latest_published.id,
                    PolicyAcceptance.user_id == user_id,
                )
            )
        ).first() is not None
    return PolicyOut(
        id=policy.id,
        name=policy.name,
        slug=policy.slug,
        description=policy.description,
        latest_version=latest_published.version if latest_published else None,
        accepted_count=accepted_count,
        accepted_by_me=accepted_by_me,
    )


async def _policy_detail(session: AsyncSession, policy: Policy, user_id: uuid.UUID) -> PolicyDetail:
    base = await _policy_out(session, policy, user_id)
    versions = (
        (
            await session.execute(
                select(PolicyVersion)
                .where(PolicyVersion.policy_id == policy.id)
                .order_by(PolicyVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return PolicyDetail(
        **base.model_dump(),
        versions=[PolicyVersionOut.model_validate(v) for v in versions],
    )


async def _get_owned(session: AsyncSession, policy_id: uuid.UUID, org_id: uuid.UUID) -> Policy:
    policy = (
        await session.execute(
            select(Policy).where(Policy.id == policy_id, Policy.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="policy not found")
    return policy


@router.post("", response_model=PolicyDetail, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreate, session: SessionDep, ctx: OwnerOrAdmin) -> PolicyDetail:
    org_id = ctx.organization.id
    policy = Policy(
        organization_id=org_id,
        name=body.name,
        slug=await _unique_slug(session, org_id, body.name, body.slug),
        description=body.description,
    )
    session.add(policy)
    await session.flush()
    session.add(
        PolicyVersion(policy_id=policy.id, version=1, body=body.body, created_by_id=ctx.user.id)
    )
    await session.commit()
    return await _policy_detail(session, policy, ctx.user.id)


@router.get("", response_model=list[PolicyOut])
async def list_policies(ctx: AuthDep, session: SessionDep) -> list[PolicyOut]:
    policies = (
        (
            await session.execute(
                select(Policy)
                .where(Policy.organization_id == ctx.organization.id)
                .order_by(Policy.name)
            )
        )
        .scalars()
        .all()
    )
    return [await _policy_out(session, p, ctx.user.id) for p in policies]


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(policy_id: uuid.UUID, ctx: AuthDep, session: SessionDep) -> PolicyDetail:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    return await _policy_detail(session, policy, ctx.user.id)


@router.post(
    "/{policy_id}/versions",
    response_model=PolicyDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_version(
    policy_id: uuid.UUID,
    body: PolicyVersionCreate,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> PolicyDetail:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    latest = await _latest_version(session, policy.id)
    next_version = (latest.version + 1) if latest else 1
    session.add(
        PolicyVersion(
            policy_id=policy.id,
            version=next_version,
            body=body.body,
            created_by_id=ctx.user.id,
            status=PolicyVersionStatus.published,
        )
    )
    await session.commit()
    return await _policy_detail(session, policy, ctx.user.id)


@router.put("/{policy_id}/versions/{version}", response_model=PolicyDetail)
async def update_version(
    policy_id: uuid.UUID,
    version: int,
    body: PolicyVersionUpdate,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> PolicyDetail:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    policy_version = (
        await session.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy.id,
                PolicyVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not policy_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="policy version not found"
        )
    if policy_version.status != PolicyVersionStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="only draft versions can be edited"
        )
    policy_version.body = body.body
    await session.commit()
    return await _policy_detail(session, policy, ctx.user.id)


@router.post("/{policy_id}/versions/{version}/publish", response_model=PolicyDetail)
async def publish_version(
    policy_id: uuid.UUID,
    version: int,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> PolicyDetail:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    policy_version = (
        await session.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy.id,
                PolicyVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not policy_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="policy version not found"
        )
    policy_version.status = PolicyVersionStatus.published
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=ctx.user.id,
        action="policy.publish",
        target_type="policy",
        target_id=policy.id,
        summary=f"published '{policy.name}' v{version}",
    )
    await session.commit()
    return await _policy_detail(session, policy, ctx.user.id)


@router.post("/{policy_id}/accept", response_model=PolicyOut)
async def accept_policy(policy_id: uuid.UUID, ctx: Members, session: SessionDep) -> PolicyOut:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    latest_published = await _latest_published_version(session, policy.id)
    if latest_published is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="policy has no versions"
        )
    already = (
        await session.execute(
            select(PolicyAcceptance).where(
                PolicyAcceptance.policy_version_id == latest_published.id,
                PolicyAcceptance.user_id == ctx.user.id,
            )
        )
    ).scalar_one_or_none()
    if already is None:
        session.add(
            PolicyAcceptance(
                policy_version_id=latest_published.id,
                user_id=ctx.user.id,
                accepted_at=datetime.now(UTC),
            )
        )
        await session.commit()
    return await _policy_out(session, policy, ctx.user.id)


@router.get("/{policy_id}/acceptances", response_model=list[AcceptanceOut])
async def list_acceptances(
    policy_id: uuid.UUID, session: SessionDep, ctx: OwnerOrAdmin
) -> list[AcceptanceOut]:
    policy = await _get_owned(session, policy_id, ctx.organization.id)
    rows = (
        await session.execute(
            select(
                PolicyAcceptance.user_id,
                PolicyVersion.version,
                PolicyAcceptance.accepted_at,
            )
            .join(PolicyVersion, PolicyAcceptance.policy_version_id == PolicyVersion.id)
            .where(PolicyVersion.policy_id == policy.id)
            .order_by(PolicyAcceptance.accepted_at.desc())
        )
    ).all()
    return [
        AcceptanceOut(user_id=user_id, version=version, accepted_at=accepted_at)
        for user_id, version, accepted_at in rows
    ]
