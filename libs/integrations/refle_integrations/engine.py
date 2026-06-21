"""Run a connection: collect resources, evaluate control tests, persist results,
update per-control posture, and open/resolve remediation tasks.

Shared by the API (manual sync) and the Celery worker (scheduled sync).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from refle_core.crypto import decrypt
from refle_core.models import (
    Connection,
    ConnectionStatus,
    Control,
    ControlStatus,
    ControlTestResult,
    OrgControl,
    RemediationStatus,
    RemediationTask,
)
from refle_extensions.registry import connector_registry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class SyncOutcome:
    ok: bool
    tests_run: int = 0
    failures: int = 0
    error: str | None = None


async def run_connection(session: AsyncSession, connection: Connection) -> SyncOutcome:
    try:
        connector = connector_registry.get(connection.provider)
    except KeyError:
        return SyncOutcome(ok=False, error=f"unknown provider: {connection.provider}")

    try:
        credentials = json.loads(decrypt(connection.encrypted_credentials) or "{}")
        auth = connector.authenticate(credentials)
        resources = connector.collect(auth)
    except Exception as exc:  # noqa: BLE001 - surface any connector failure on the connection
        connection.status = ConnectionStatus.error
        connection.last_error = str(exc)
        await session.commit()
        return SyncOutcome(ok=False, error=str(exc))

    results_by_code: dict[str, list[bool]] = {}
    tests_run = 0
    for test in connector.tests:
        outcome = test.run(resources)
        tests_run += 1
        for code in test.control_codes:
            session.add(
                ControlTestResult(
                    organization_id=connection.organization_id,
                    connection_id=connection.id,
                    test_key=test.key,
                    control_code=code,
                    passed=outcome.passed,
                    detail=outcome.detail,
                )
            )
            results_by_code.setdefault(code, []).append(outcome.passed)

    failures = await _apply_to_controls(session, connection.organization_id, results_by_code)

    connection.status = ConnectionStatus.connected
    connection.last_synced_at = datetime.now(UTC)
    connection.last_error = None
    await session.commit()
    return SyncOutcome(ok=True, tests_run=tests_run, failures=failures)


async def _apply_to_controls(
    session: AsyncSession, org_id, results_by_code: dict[str, list[bool]]
) -> int:
    failures = 0
    for code, passes in results_by_code.items():
        all_passed = all(passes)
        if not all_passed:
            failures += 1

        org_control = (
            await session.execute(
                select(OrgControl)
                .join(Control, OrgControl.control_id == Control.id)
                .where(OrgControl.organization_id == org_id, Control.code == code)
            )
        ).scalar_one_or_none()
        if org_control is not None:
            org_control.status = ControlStatus.passing if all_passed else ControlStatus.failing

        open_tasks = (
            (
                await session.execute(
                    select(RemediationTask).where(
                        RemediationTask.organization_id == org_id,
                        RemediationTask.control_code == code,
                        RemediationTask.status == RemediationStatus.open,
                    )
                )
            )
            .scalars()
            .all()
        )

        if not all_passed and not open_tasks:
            session.add(
                RemediationTask(
                    organization_id=org_id,
                    control_code=code,
                    title=f"Remediate {code}",
                    detail="An automated control test failed.",
                    status=RemediationStatus.open,
                    source="automated",
                )
            )
        elif all_passed:
            for task in open_tasks:
                task.status = RemediationStatus.resolved

    return failures
