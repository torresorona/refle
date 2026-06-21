"""Integration connections: connector catalog, connect, sync, results, remediation."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, status
from refle_core.crypto import encrypt
from refle_core.models import (
    Connection,
    ControlTestResult,
    RemediationStatus,
    RemediationTask,
)
from refle_extensions.registry import connector_registry
from refle_integrations.engine import run_connection
from sqlalchemy import select

from refle_api.deps import AuthDep, OwnerOrAdmin, SessionDep
from refle_api.notify import dispatch_notifications
from refle_api.schemas import (
    ConnectionCreate,
    ConnectionOut,
    ConnectionUpdate,
    ConnectorInfo,
    RemediationTaskOut,
    SyncResult,
    TestResultOut,
)

router = APIRouter(tags=["integrations"])


@router.get("/integrations/connectors", response_model=list[ConnectorInfo])
async def list_connectors(ctx: AuthDep) -> list[ConnectorInfo]:
    infos = [
        ConnectorInfo(
            key=key,
            name=c.name,
            description=c.description,
            credential_fields=list(c.credential_fields),
        )
        for key, c in connector_registry.all().items()
    ]
    return sorted(infos, key=lambda i: i.name)


@router.post("/connections", response_model=ConnectionOut, status_code=status.HTTP_201_CREATED)
async def create_connection(
    body: ConnectionCreate, session: SessionDep, ctx: OwnerOrAdmin
) -> ConnectionOut:
    if body.provider not in connector_registry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown provider: {body.provider}"
        )
    conn = Connection(
        organization_id=ctx.organization.id,
        provider=body.provider,
        label=body.label,
        encrypted_credentials=encrypt(json.dumps(body.credentials)),
        created_by_id=ctx.user.id,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)
    return ConnectionOut.model_validate(conn)


@router.get("/connections", response_model=list[ConnectionOut])
async def list_connections(ctx: AuthDep, session: SessionDep) -> list[ConnectionOut]:
    rows = (
        (
            await session.execute(
                select(Connection)
                .where(Connection.organization_id == ctx.organization.id)
                .order_by(Connection.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [ConnectionOut.model_validate(c) for c in rows]


@router.patch("/connections/{connection_id}", response_model=ConnectionOut)
async def update_connection(
    connection_id: uuid.UUID, body: ConnectionUpdate, session: SessionDep, ctx: OwnerOrAdmin
) -> ConnectionOut:
    conn = await _get_owned(session, connection_id, ctx.organization.id)
    if body.monitoring_enabled is not None:
        conn.monitoring_enabled = body.monitoring_enabled
    if body.sync_interval_minutes is not None:
        conn.sync_interval_minutes = body.sync_interval_minutes
    await session.commit()
    await session.refresh(conn)
    return ConnectionOut.model_validate(conn)


@router.post("/connections/{connection_id}/sync", response_model=SyncResult)
async def sync_connection(
    connection_id: uuid.UUID, session: SessionDep, ctx: OwnerOrAdmin
) -> SyncResult:
    conn = await _get_owned(session, connection_id, ctx.organization.id)
    outcome = await run_connection(session, conn)
    if outcome.notifications:
        await dispatch_notifications(session, outcome.notifications)
    return SyncResult(
        ok=outcome.ok,
        tests_run=outcome.tests_run,
        failures=outcome.failures,
        error=outcome.error,
    )


@router.get("/connections/{connection_id}/results", response_model=list[TestResultOut])
async def connection_results(
    connection_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> list[TestResultOut]:
    await _get_owned(session, connection_id, ctx.organization.id)
    rows = (
        (
            await session.execute(
                select(ControlTestResult)
                .where(ControlTestResult.connection_id == connection_id)
                .order_by(ControlTestResult.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [TestResultOut.model_validate(r) for r in rows]


@router.get("/remediation-tasks", response_model=list[RemediationTaskOut])
async def remediation_tasks(ctx: AuthDep, session: SessionDep) -> list[RemediationTaskOut]:
    rows = (
        (
            await session.execute(
                select(RemediationTask)
                .where(
                    RemediationTask.organization_id == ctx.organization.id,
                    RemediationTask.status == RemediationStatus.open,
                )
                .order_by(RemediationTask.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [RemediationTaskOut.model_validate(r) for r in rows]


async def _get_owned(session, connection_id: uuid.UUID, org_id: uuid.UUID) -> Connection:
    conn = (
        await session.execute(
            select(Connection).where(
                Connection.id == connection_id, Connection.organization_id == org_id
            )
        )
    ).scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connection not found")
    return conn
