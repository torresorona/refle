"""Controls catalog, per-org control status, and posture summary (tenant-scoped)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from refle_core.models import Control, ControlStatus, Framework, OrgControl
from sqlalchemy import func, select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.schemas import (
    ControlOut,
    OrgControlOut,
    OrgControlUpdate,
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

    if body.status is not None:
        oc.status = body.status
    if body.owner_id is not None:
        oc.owner_id = body.owner_id
    await session.commit()

    control = await session.get(Control, oc.control_id)
    return OrgControlOut(
        id=oc.id,
        control=ControlOut.model_validate(control),
        status=oc.status,
        owner_id=oc.owner_id,
    )


@router.get("/posture", response_model=PostureSummary)
async def posture(ctx: AuthDep, session: SessionDep) -> PostureSummary:
    rows = (
        await session.execute(
            select(OrgControl.status, func.count())
            .where(OrgControl.organization_id == ctx.organization.id)
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
