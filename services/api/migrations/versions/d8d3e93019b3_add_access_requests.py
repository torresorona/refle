"""add access requests

Revision ID: d8d3e93019b3
Revises: b4538924eeda
Create Date: 2026-06-21 15:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d8d3e93019b3"
down_revision: str | None = "b4538924eeda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_requests",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "admin", "member", "auditor", name="role", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="access_request_status"),
            nullable=False,
        ),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "email", "status"),
    )
    op.create_index(op.f("ix_access_requests_email"), "access_requests", ["email"], unique=False)
    op.create_index(
        op.f("ix_access_requests_organization_id"),
        "access_requests",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_access_requests_organization_id"), table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_email"), table_name="access_requests")
    op.drop_table("access_requests")
    op.execute("DROP TYPE IF EXISTS access_request_status")
