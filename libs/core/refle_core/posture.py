"""Shared posture aggregation over ``OrgControl`` status.

Used by the controls posture endpoint, the readiness reports, and the sync
engine (which records a ``PostureSnapshot`` for trend history).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_core.models import ControlStatus, OrgControl


@dataclass
class PostureCounts:
    passing: int
    failing: int
    not_assessed: int

    @property
    def total(self) -> int:
        return self.passing + self.failing + self.not_assessed

    @property
    def percent_ready(self) -> int:
        return round(self.passing / self.total * 100) if self.total else 0


async def posture_counts(session: AsyncSession, org_id: uuid.UUID) -> PostureCounts:
    rows = (
        await session.execute(
            select(OrgControl.status, func.count())
            .where(OrgControl.organization_id == org_id)
            .group_by(OrgControl.status)
        )
    ).all()
    counts = {status: n for status, n in rows}
    return PostureCounts(
        passing=counts.get(ControlStatus.passing, 0),
        failing=counts.get(ControlStatus.failing, 0),
        not_assessed=counts.get(ControlStatus.not_assessed, 0),
    )
