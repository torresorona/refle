"""sans crf policy templates

Revision ID: e4c9a07d6f32
Revises: d8d3e93019b3
Create Date: 2026-06-21 16:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import yaml
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4c9a07d6f32"
down_revision: str | None = "d8d3e93019b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_TEMPLATE_NAMES = ("SANS Access Control Policy",)


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[4] / "content" / "policy_templates" / "sans_crf.yaml"


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


def _load_templates() -> tuple[str, list[dict[str, Any]]]:
    data = yaml.safe_load(_catalog_path().read_text())
    return data["source"], data["templates"]


def upgrade() -> None:
    source_name, templates = _load_templates()
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM policy_templates "
            "WHERE organization_id IS NULL AND name IN :legacy_names"
        ).bindparams(sa.bindparam("legacy_names", expanding=True)),
        {"legacy_names": list(_LEGACY_TEMPLATE_NAMES)},
    )

    for item in templates:
        values = {
            "name": item["name"],
            "description": _template_description(item),
            "body": _template_body(item, source_name),
        }
        updated = conn.execute(
            sa.text(
                "UPDATE policy_templates "
                "SET description = :description, body = :body, type = 'builtin', updated_at = now() "
                "WHERE organization_id IS NULL AND name = :name"
            ),
            values,
        )
        if updated.rowcount == 0:
            conn.execute(
                sa.text(
                    "INSERT INTO policy_templates "
                    "(id, name, description, body, type, organization_id, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :name, :description, :body, 'builtin', NULL, now(), now())"
                ),
                values,
            )


def downgrade() -> None:
    _, templates = _load_templates()
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM policy_templates "
            "WHERE organization_id IS NULL AND name IN :template_names"
        ).bindparams(sa.bindparam("template_names", expanding=True)),
        {"template_names": [item["name"] for item in templates]},
    )
