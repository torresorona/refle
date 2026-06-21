"""Audit-readiness reports and the exportable audit package."""

from __future__ import annotations

from fastapi import APIRouter, Response

from refle_api import readiness
from refle_api.deps import AuthDep, SessionDep
from refle_api.schemas import (
    ControlCoverageOut,
    FrameworkProgressOut,
    GapOut,
    ReadinessReport,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/readiness", response_model=ReadinessReport)
async def get_readiness(ctx: AuthDep, session: SessionDep) -> ReadinessReport:
    org_id = ctx.organization.id
    fp = await readiness.framework_progress(session, org_id)
    coverage = await readiness.control_coverage(session, org_id)
    return ReadinessReport(
        framework=FrameworkProgressOut.model_validate(fp),
        controls=[ControlCoverageOut.model_validate(c) for c in coverage],
    )


@router.get("/gaps", response_model=list[GapOut])
async def get_gaps(ctx: AuthDep, session: SessionDep) -> list[GapOut]:
    gaps = await readiness.compute_gaps(session, ctx.organization.id)
    return [GapOut.model_validate(g) for g in gaps]


@router.get("/audit-package")
async def audit_package(ctx: AuthDep, session: SessionDep) -> Response:
    from refle_core.config import get_settings

    data = await readiness.build_audit_package(
        session, ctx.organization, get_settings().edition
    )
    filename = f"refle-audit-package-{ctx.organization.slug}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
