"""Reusable business logic shared across routers."""

from __future__ import annotations

import re
import secrets
import uuid

from refle_core.models import Control, Framework, OrgControl
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

SOC2_FRAMEWORK_KEY = "soc2"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "org"


async def unique_org_slug(session: AsyncSession, name: str) -> str:
    """Return a slug for ``name`` that doesn't collide with an existing org."""
    from refle_core.models import Organization

    base = slugify(name)
    candidate = base
    while (
        await session.execute(select(Organization.id).where(Organization.slug == candidate))
    ).first() is not None:
        candidate = f"{base}-{secrets.token_hex(3)}"
    return candidate


def new_invite_token() -> str:
    return secrets.token_urlsafe(32)


async def bootstrap_org_controls(session: AsyncSession, organization_id: uuid.UUID) -> int:
    """Create OrgControl rows for every SOC 2 control the org doesn't have yet.

    Idempotent. Returns the number of rows created. No-op if the catalog isn't
    seeded yet (see ``refle_api.seed``).
    """
    framework = (
        await session.execute(select(Framework).where(Framework.key == SOC2_FRAMEWORK_KEY))
    ).scalar_one_or_none()
    if framework is None:
        return 0

    control_ids = (
        (await session.execute(select(Control.id).where(Control.framework_id == framework.id)))
        .scalars()
        .all()
    )

    existing = set(
        (
            await session.execute(
                select(OrgControl.control_id).where(OrgControl.organization_id == organization_id)
            )
        )
        .scalars()
        .all()
    )

    created = 0
    for control_id in control_ids:
        if control_id in existing:
            continue
        session.add(OrgControl(organization_id=organization_id, control_id=control_id))
        created += 1
    await session.flush()
    return created


async def count_controls(session: AsyncSession) -> int:
    return (await session.execute(select(func.count(Control.id)))).scalar_one()
