"""Controls catalog, per-org control status, and posture summary (tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from refle_core.audit import record_audit
from refle_core.models import Control, ControlStatus, Framework, OrgControl, PostureSnapshot
from sqlalchemy import func, select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.schemas import (
    ControlOut,
    OrgControlOut,
    OrgControlUpdate,
    PostureSnapshotOut,
    PostureSummary,
)
from refle_api.services import SOC2_FRAMEWORK_KEY, bootstrap_org_controls

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("/catalog", response_model=list[ControlOut])
async def catalog(ctx: AuthDep, session: SessionDep) -> list[ControlOut]:
    rows = (
        (
            await session.execute(
                select(Control)
                .join(Framework, Control.framework_id == Framework.id)
                .where(Framework.key == SOC2_FRAMEWORK_KEY)
                .order_by(Control.code)
            )
        )
        .scalars()
        .all()
    )
    return [ControlOut.model_validate(c) for c in rows]


@router.get("", response_model=list[OrgControlOut])
async def list_org_controls(ctx: AuthDep, session: SessionDep) -> list[OrgControlOut]:
    org_id = ctx.organization.id
    count = (
        await session.execute(
            select(func.count(OrgControl.id)).where(OrgControl.organization_id == org_id)
        )
    ).scalar_one()
    if count == 0:
        if await bootstrap_org_controls(session, org_id):
            await session.commit()

    rows = (
        await session.execute(
            select(OrgControl, Control)
            .join(Control, OrgControl.control_id == Control.id)
            .where(OrgControl.organization_id == org_id)
            .order_by(Control.code)
        )
    ).all()
    return [
        OrgControlOut(
            id=oc.id,
            control=ControlOut.model_validate(c),
            status=oc.status,
            owner_id=oc.owner_id,
            in_scope=oc.in_scope,
        )
        for oc, c in rows
    ]


@router.patch("/{org_control_id}", response_model=OrgControlOut)
async def update_org_control(
    org_control_id: uuid.UUID,
    body: OrgControlUpdate,
    session: SessionDep,
    ctx: OwnerOrAdmin,
) -> OrgControlOut:
    oc = (
        await session.execute(
            select(OrgControl).where(
                OrgControl.id == org_control_id,
                OrgControl.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if oc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")

    control = await session.get(Control, oc.control_id)
    if body.status is not None:
        oc.status = body.status
        await record_audit(
            session,
            organization_id=ctx.organization.id,
            actor_id=ctx.user.id,
            action="control.status",
            target_type="control",
            target_id=control.code if control else oc.control_id,
            summary=f"status set to {body.status.value}",
        )
    if body.owner_id is not None:
        oc.owner_id = body.owner_id
    if body.in_scope is not None and body.in_scope != oc.in_scope:
        oc.in_scope = body.in_scope
        await record_audit(
            session,
            organization_id=ctx.organization.id,
            actor_id=ctx.user.id,
            action="control.scope",
            target_type="control",
            target_id=control.code if control else oc.control_id,
            summary=("marked in scope" if body.in_scope else "marked out of scope"),
        )
    await session.commit()

    return OrgControlOut(
        id=oc.id,
        control=ControlOut.model_validate(control),
        status=oc.status,
        owner_id=oc.owner_id,
        in_scope=oc.in_scope,
    )


@router.get("/posture", response_model=PostureSummary)
async def posture(ctx: AuthDep, session: SessionDep) -> PostureSummary:
    rows = (
        await session.execute(
            select(OrgControl.status, func.count())
            .where(
                OrgControl.organization_id == ctx.organization.id,
                OrgControl.in_scope.is_(True),
            )
            .group_by(OrgControl.status)
        )
    ).all()
    counts = {s: n for s, n in rows}
    passing = counts.get(ControlStatus.passing, 0)
    failing = counts.get(ControlStatus.failing, 0)
    not_assessed = counts.get(ControlStatus.not_assessed, 0)
    total = passing + failing + not_assessed
    pct = round(passing / total * 100, 1) if total else 0.0
    return PostureSummary(
        total=total,
        passing=passing,
        failing=failing,
        not_assessed=not_assessed,
        percent_passing=pct,
    )


@router.get("/posture/history", response_model=list[PostureSnapshotOut])
async def posture_history(
    ctx: AuthDep, session: SessionDep, days: int = 30
) -> list[PostureSnapshotOut]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(PostureSnapshot)
                .where(
                    PostureSnapshot.organization_id == ctx.organization.id,
                    PostureSnapshot.created_at >= since,
                )
                .order_by(PostureSnapshot.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [PostureSnapshotOut.model_validate(r) for r in rows]
