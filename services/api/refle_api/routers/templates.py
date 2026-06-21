"""Templates management: built-in and custom templates for policy drafting."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, status
from refle_core.models import PolicyTemplate, TemplateType
from sqlalchemy import select

from refle_api.deps import AuthDep, Members, SessionDep
from refle_api.schemas import PolicyTemplateDetailOut, PolicyTemplateOut

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[PolicyTemplateOut])
async def list_templates(ctx: AuthDep, session: SessionDep) -> list[PolicyTemplateOut]:
    """List globally built-in templates and the organization's custom templates."""
    items = (
        (
            await session.execute(
                select(PolicyTemplate)
                .where(
                    (PolicyTemplate.organization_id.is_(None))
                    | (PolicyTemplate.organization_id == ctx.organization.id)
                )
                .order_by(PolicyTemplate.name)
            )
        )
        .scalars()
        .all()
    )
    return items


@router.post("", response_model=PolicyTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    session: SessionDep,
    ctx: Members,
    name: Annotated[str, Form()],
    body: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> PolicyTemplateOut:
    """Create a new custom template from text."""
    tpl = PolicyTemplate(
        organization_id=ctx.organization.id,
        name=name,
        description=description,
        body=body,
        type=TemplateType.custom,
    )
    session.add(tpl)
    await session.commit()
    return tpl


@router.get("/{template_id}", response_model=PolicyTemplateDetailOut)
async def get_template(
    template_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> PolicyTemplateDetailOut:
    tpl = (
        await session.execute(
            select(PolicyTemplate).where(
                PolicyTemplate.id == template_id,
                (PolicyTemplate.organization_id.is_(None))
                | (PolicyTemplate.organization_id == ctx.organization.id),
            )
        )
    ).scalar_one_or_none()

    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    return tpl
