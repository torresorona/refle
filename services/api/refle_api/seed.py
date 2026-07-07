"""Seed content catalogs into the database.

Run with: ``make seed`` (or ``uv run python -m refle_api.seed``). Idempotent.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml
from refle_core.db import get_sessionmaker
from refle_core.models import Control, Framework, PolicyTemplate, TemplateType
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

_DEFAULT_CONTROLS = (
    Path(__file__).resolve().parents[3] / "content" / "frameworks" / "soc2" / "controls.yaml"
)
_DEFAULT_CONTENT = _DEFAULT_CONTROLS
_DEFAULT_POLICY_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "content" / "policy_templates" / "sans_crf.yaml"
)
_LEGACY_TEMPLATE_NAMES = {"SANS Access Control Policy"}


async def seed_soc2(session: AsyncSession, path: Path | None = None) -> dict[str, Any]:
    path = path or _DEFAULT_CONTROLS
    data = yaml.safe_load(path.read_text())
    fw = data["framework"]

    framework = (
        await session.execute(select(Framework).where(Framework.key == fw["key"]))
    ).scalar_one_or_none()
    if framework is None:
        framework = Framework(key=fw["key"], name=fw["name"], version=fw.get("version"))
        session.add(framework)
        await session.flush()
    else:
        framework.name = fw["name"]
        framework.version = fw.get("version")

    existing = {
        c.code: c
        for c in (
            await session.execute(select(Control).where(Control.framework_id == framework.id))
        )
        .scalars()
        .all()
    }

    created = updated = 0
    for item in data["controls"]:
        control = existing.get(item["code"])
        description = (item.get("description") or "").strip() or None
        if control is None:
            session.add(
                Control(
                    framework_id=framework.id,
                    code=item["code"],
                    title=item["title"],
                    description=description,
                    category=item.get("category"),
                )
            )
            created += 1
        else:
            control.title = item["title"]
            control.description = description
            control.category = item.get("category")
            updated += 1

    await session.commit()
    return {"framework": framework.key, "created": created, "updated": updated}


def _template_description(item: dict[str, Any]) -> str:
    return (
        f"SANS/CRF {item['category']} template. "
        f"Authoritative source: {item['source_url']}"
    )


def _template_body(item: dict[str, Any], source_name: str) -> str:
    name = item["name"]
    return f"""# {name}

> Refle starter based on the {source_name} catalog entry. Review the authoritative
> SANS/CRF source before adopting this policy.

## Purpose
Define the organization's expectations, ownership, and minimum requirements for {name}.

## Scope
This policy applies to relevant personnel, systems, services, data, vendors, and processes
that support the organization's security and compliance program.

## Policy Requirements
- Assign an accountable owner for this policy and the related control activities.
- Document the systems, data, processes, and roles covered by this policy.
- Define required approvals, review cadence, evidence expectations, and exception handling.
- Maintain records that demonstrate implementation and operating effectiveness.
- Review this policy at least annually or after material changes to the business, systems,
  regulatory obligations, or threat environment.

## Roles and Responsibilities
- Owner: maintains the policy, approves exceptions, and reviews evidence.
- Operators: implement and maintain the required procedures.
- Users: follow the policy and report suspected violations or weaknesses.

## Exceptions
Exceptions must be documented, risk accepted by the policy owner, time-bound, and reviewed
before expiration.

## Source
- SANS/CRF template page: {item['source_url']}
- PDF: {item['pdf_url']}
- DOCX: {item['docx_url']}
"""


async def seed_policy_templates(
    session: AsyncSession, path: Path | None = None
) -> dict[str, Any]:
    path = path or _DEFAULT_POLICY_TEMPLATES
    data = yaml.safe_load(path.read_text())
    source_name = data["source"]
    templates = data["templates"]

    await session.execute(
        delete(PolicyTemplate).where(
            PolicyTemplate.organization_id.is_(None),
            PolicyTemplate.name.in_(_LEGACY_TEMPLATE_NAMES),
        )
    )

    existing = {
        template.name: template
        for template in (
            await session.execute(
                select(PolicyTemplate).where(PolicyTemplate.organization_id.is_(None))
            )
        )
        .scalars()
        .all()
    }

    created = updated = 0
    for item in templates:
        body = _template_body(item, source_name)
        description = _template_description(item)
        template = existing.get(item["name"])
        if template is None:
            session.add(
                PolicyTemplate(
                    name=item["name"],
                    description=description,
                    body=body,
                    type=TemplateType.builtin,
                    organization_id=None,
                )
            )
            created += 1
        else:
            template.description = description
            template.body = body
            template.type = TemplateType.builtin
            updated += 1

    await session.commit()
    return {"source": source_name, "created": created, "updated": updated, "total": len(templates)}


async def _main() -> None:
    async with get_sessionmaker()() as session:
        controls = await seed_soc2(session)
        templates = await seed_policy_templates(session)
    print(
        f"seeded {controls['framework']}: +{controls['created']} created, "
        f"{controls['updated']} updated"
    )
    print(
        f"seeded {templates['source']} templates: +{templates['created']} created, "
        f"{templates['updated']} updated ({templates['total']} total)"
    )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
