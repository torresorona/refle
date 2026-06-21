"""Evidence upload (to object storage) and mapping to org controls."""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from refle_core.models import Control, Evidence, EvidenceControl, OrgControl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_api import storage
from refle_api.deps import AuthDep, Members, OwnerOrAdmin, SessionDep
from refle_api.schemas import DownloadUrl, EvidenceOut

router = APIRouter(prefix="/evidence", tags=["evidence"])


def _parse_ids(raw: str | None) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(uuid.UUID(part))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"invalid control id: {part}",
            ) from exc
    return ids


async def _codes_by_evidence(
    session: AsyncSession, evidence_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    if not evidence_ids:
        return {}
    rows = (
        await session.execute(
            select(EvidenceControl.evidence_id, Control.code)
            .join(OrgControl, EvidenceControl.org_control_id == OrgControl.id)
            .join(Control, OrgControl.control_id == Control.id)
            .where(EvidenceControl.evidence_id.in_(evidence_ids))
        )
    ).all()
    mapping: dict[uuid.UUID, list[str]] = {}
    for evidence_id, code in rows:
        mapping.setdefault(evidence_id, []).append(code)
    for codes in mapping.values():
        codes.sort()
    return mapping


def _to_out(ev: Evidence, codes: list[str]) -> EvidenceOut:
    return EvidenceOut(
        id=ev.id,
        name=ev.name,
        description=ev.description,
        filename=ev.filename,
        content_type=ev.content_type,
        size_bytes=ev.size_bytes,
        source=ev.source,
        uploaded_by_id=ev.uploaded_by_id,
        control_codes=codes,
        created_at=ev.created_at,
    )


@router.post("", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    session: SessionDep,
    ctx: Members,
    file: Annotated[UploadFile, File()],
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    control_ids: Annotated[str | None, Form()] = None,
) -> EvidenceOut:
    org_id = ctx.organization.id
    requested = _parse_ids(control_ids)

    valid_ids: list[uuid.UUID] = []
    if requested:
        valid_ids = list(
            (
                await session.execute(
                    select(OrgControl.id).where(
                        OrgControl.id.in_(requested),
                        OrgControl.organization_id == org_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        missing = set(requested) - set(valid_ids)
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown control(s): {sorted(str(m) for m in missing)}",
            )

    data = await file.read()
    filename = file.filename or "upload.bin"
    key = f"{org_id}/{uuid.uuid4()}/{filename}"
    await run_in_threadpool(storage.ensure_bucket)
    await run_in_threadpool(storage.put_object, key, data, file.content_type)

    ev = Evidence(
        organization_id=org_id,
        name=name,
        description=description,
        object_key=key,
        filename=filename,
        content_type=file.content_type,
        size_bytes=len(data),
        content_sha256=hashlib.sha256(data).hexdigest(),
        uploaded_by_id=ctx.user.id,
    )
    session.add(ev)
    await session.flush()
    for control_id in valid_ids:
        session.add(EvidenceControl(evidence_id=ev.id, org_control_id=control_id))
    await session.commit()

    codes = (await _codes_by_evidence(session, [ev.id])).get(ev.id, [])
    return _to_out(ev, codes)


@router.get("", response_model=list[EvidenceOut])
async def list_evidence(ctx: AuthDep, session: SessionDep) -> list[EvidenceOut]:
    items = (
        (
            await session.execute(
                select(Evidence)
                .where(Evidence.organization_id == ctx.organization.id)
                .order_by(Evidence.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    codes = await _codes_by_evidence(session, [e.id for e in items])
    return [_to_out(e, codes.get(e.id, [])) for e in items]


@router.get("/{evidence_id}/download", response_model=DownloadUrl)
async def download_evidence(
    evidence_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> DownloadUrl:
    ev = await _get_owned(session, evidence_id, ctx.organization.id)
    url = await run_in_threadpool(storage.presigned_get, ev.object_key)
    return DownloadUrl(url=url)


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(evidence_id: uuid.UUID, session: SessionDep, ctx: OwnerOrAdmin) -> None:
    ev = await _get_owned(session, evidence_id, ctx.organization.id)
    key = ev.object_key
    await session.delete(ev)
    await session.commit()
    await run_in_threadpool(storage.delete_object, key)


async def _get_owned(session: AsyncSession, evidence_id: uuid.UUID, org_id: uuid.UUID) -> Evidence:
    ev = (
        await session.execute(
            select(Evidence).where(Evidence.id == evidence_id, Evidence.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if ev is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evidence not found")
    return ev
