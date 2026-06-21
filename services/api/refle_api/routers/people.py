"""People: employees, on/offboarding checklists, and security-training records."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, status
from refle_core.models import ChecklistItem, ChecklistKind, Person, PersonStatus, TrainingRecord
from refle_core.models.people import DEFAULT_OFFBOARDING, DEFAULT_ONBOARDING
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from refle_api.deps import AuthDep, Members, SessionDep
from refle_api.schemas import (
    ChecklistItemOut,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    TrainingCreate,
    TrainingOut,
)

router = APIRouter(prefix="/people", tags=["people"])


def _checklist_items(person: Person, kind: ChecklistKind) -> list[ChecklistItem]:
    labels = DEFAULT_ONBOARDING if kind == ChecklistKind.onboarding else DEFAULT_OFFBOARDING
    return [
        ChecklistItem(
            organization_id=person.organization_id, person_id=person.id, kind=kind, label=label
        )
        for label in labels
    ]


async def _get_person(session: AsyncSession, person_id: uuid.UUID, org_id: uuid.UUID) -> Person:
    p = (
        await session.execute(
            select(Person).where(Person.id == person_id, Person.organization_id == org_id)
        )
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person not found")
    return p


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(body: PersonCreate, session: SessionDep, ctx: Members) -> PersonOut:
    person = Person(
        organization_id=ctx.organization.id,
        full_name=body.full_name,
        email=body.email,
        title=body.title,
        start_date=body.start_date,
        manager_id=body.manager_id,
    )
    session.add(person)
    await session.flush()
    for item in _checklist_items(person, ChecklistKind.onboarding):
        session.add(item)
    await session.commit()
    await session.refresh(person)
    return PersonOut.model_validate(person)


@router.get("", response_model=list[PersonOut])
async def list_people(ctx: AuthDep, session: SessionDep) -> list[PersonOut]:
    rows = (
        (
            await session.execute(
                select(Person)
                .where(Person.organization_id == ctx.organization.id)
                .order_by(Person.full_name)
            )
        )
        .scalars()
        .all()
    )
    return [PersonOut.model_validate(p) for p in rows]


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: uuid.UUID, ctx: AuthDep, session: SessionDep) -> PersonOut:
    return PersonOut.model_validate(await _get_person(session, person_id, ctx.organization.id))


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: uuid.UUID, body: PersonUpdate, session: SessionDep, ctx: Members
) -> PersonOut:
    person = await _get_person(session, person_id, ctx.organization.id)
    terminating = (
        body.status == PersonStatus.terminated and person.status != PersonStatus.terminated
    )
    if body.full_name is not None:
        person.full_name = body.full_name
    if body.title is not None:
        person.title = body.title
    if body.manager_id is not None:
        person.manager_id = body.manager_id
    if body.status is not None:
        person.status = body.status
    if body.end_date is not None:
        person.end_date = body.end_date

    if terminating:
        if person.end_date is None:
            person.end_date = date.today()
        existing = (
            await session.execute(
                select(ChecklistItem.id).where(
                    ChecklistItem.person_id == person.id,
                    ChecklistItem.kind == ChecklistKind.offboarding,
                )
            )
        ).first()
        if existing is None:
            for item in _checklist_items(person, ChecklistKind.offboarding):
                session.add(item)

    await session.commit()
    await session.refresh(person)
    return PersonOut.model_validate(person)


@router.get("/{person_id}/checklist", response_model=list[ChecklistItemOut])
async def list_checklist(
    person_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> list[ChecklistItemOut]:
    await _get_person(session, person_id, ctx.organization.id)
    rows = (
        (
            await session.execute(
                select(ChecklistItem)
                .where(ChecklistItem.person_id == person_id)
                .order_by(ChecklistItem.kind, ChecklistItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [ChecklistItemOut.model_validate(r) for r in rows]


@router.post("/checklist-items/{item_id}/complete", response_model=ChecklistItemOut)
async def complete_checklist_item(
    item_id: uuid.UUID, ctx: Members, session: SessionDep
) -> ChecklistItemOut:
    item = (
        await session.execute(
            select(ChecklistItem).where(
                ChecklistItem.id == item_id,
                ChecklistItem.organization_id == ctx.organization.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    if item.done_at is None:
        item.done_at = datetime.now(UTC)
        item.done_by_id = ctx.user.id
        await session.commit()
        await session.refresh(item)
    return ChecklistItemOut.model_validate(item)


@router.post(
    "/{person_id}/training", response_model=TrainingOut, status_code=status.HTTP_201_CREATED
)
async def add_training(
    person_id: uuid.UUID, body: TrainingCreate, session: SessionDep, ctx: Members
) -> TrainingOut:
    await _get_person(session, person_id, ctx.organization.id)
    record = TrainingRecord(
        organization_id=ctx.organization.id,
        person_id=person_id,
        course=body.course,
        completed_at=body.completed_at,
        expires_at=body.expires_at,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return TrainingOut.model_validate(record)


@router.get("/{person_id}/training", response_model=list[TrainingOut])
async def list_training(
    person_id: uuid.UUID, ctx: AuthDep, session: SessionDep
) -> list[TrainingOut]:
    await _get_person(session, person_id, ctx.organization.id)
    rows = (
        (
            await session.execute(
                select(TrainingRecord)
                .where(TrainingRecord.person_id == person_id)
                .order_by(TrainingRecord.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [TrainingOut.model_validate(r) for r in rows]
