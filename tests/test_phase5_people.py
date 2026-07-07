"""Phase 5C — people, on/offboarding checklists, training, access reviews."""

import uuid
from datetime import date, timedelta

import pytest
from conftest import db_available
from refle_core.db import get_sessionmaker
from refle_core.security import create_access_token, hash_password

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


async def _register(client) -> dict[str, str]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _person(client, headers, **extra) -> str:
    body = {"full_name": "Ada Lovelace", "email": f"p-{uuid.uuid4().hex[:8]}@example.com"}
    body.update(extra)
    r = await client.post("/people", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_create_person_seeds_onboarding_checklist(client):
    headers = await _register(client)
    pid = await _person(client, headers, title="Engineer")

    checklist = (await client.get(f"/people/{pid}/checklist", headers=headers)).json()
    assert len(checklist) == 5
    assert all(i["kind"] == "onboarding" for i in checklist)
    assert all(i["done_at"] is None for i in checklist)

    done = await client.post(
        f"/people/checklist-items/{checklist[0]['id']}/complete", headers=headers
    )
    assert done.status_code == 200
    assert done.json()["done_at"] is not None


async def test_terminate_creates_offboarding_and_gap(client):
    headers = await _register(client)
    pid = await _person(client, headers)

    upd = await client.patch(f"/people/{pid}", headers=headers, json={"status": "terminated"})
    assert upd.status_code == 200
    assert upd.json()["status"] == "terminated"
    assert upd.json()["end_date"] is not None

    checklist = (await client.get(f"/people/{pid}/checklist", headers=headers)).json()
    offboarding = [i for i in checklist if i["kind"] == "offboarding"]
    assert len(offboarding) == 5

    gaps = (await client.get("/reports/gaps", headers=headers)).json()
    assert any(g["kind"] == "offboarding_incomplete" for g in gaps)


async def test_expired_training_surfaces_as_gap(client):
    headers = await _register(client)
    pid = await _person(client, headers)

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    t = await client.post(
        f"/people/{pid}/training",
        headers=headers,
        json={
            "course": "Security Awareness",
            "completed_at": "2020-01-01",
            "expires_at": yesterday,
        },
    )
    assert t.status_code == 201

    gaps = (await client.get("/reports/gaps", headers=headers)).json()
    assert any(g["kind"] == "training_expired" for g in gaps)


async def test_access_review_flow_revoke_opens_remediation(client):
    headers = await _register(client)
    pid = await _person(client, headers)

    review = await client.post(
        "/access-reviews",
        headers=headers,
        json={
            "name": "Q3 Access Review",
            "items": [{"system": "okta", "person_id": pid, "access_detail": "admin"}],
        },
    )
    assert review.status_code == 201
    rid = review.json()["id"]
    items = review.json()["items"]
    assert len(items) == 1
    assert items[0]["decision"] == "pending"

    dec = await client.post(
        f"/access-reviews/items/{items[0]['id']}/decision",
        headers=headers,
        json={"decision": "revoke"},
    )
    assert dec.status_code == 200
    assert dec.json()["decision"] == "revoke"
    assert dec.json()["reviewed_at"] is not None

    tasks = (await client.get("/remediation-tasks", headers=headers)).json()
    assert any(t["title"].startswith("Revoke access") for t in tasks)

    completed = await client.post(f"/access-reviews/{rid}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


async def test_cross_tenant_person_references_are_rejected(client):
    headers_a = await _register(client)
    org_a_person = await _person(client, headers_a)

    async with get_sessionmaker()() as session:
        from refle_core.models import Membership, Organization, Role, User

        org_b = Organization(name="Manual second org", slug=f"manual-{uuid.uuid4().hex[:8]}")
        user_b = User(
            email=f"b-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("supersecret123"),
        )
        session.add_all([org_b, user_b])
        await session.flush()
        session.add(Membership(organization_id=org_b.id, user_id=user_b.id, role=Role.owner))
        await session.commit()
        token_b = create_access_token(str(user_b.id), extra={"org_id": str(org_b.id)})

    client.cookies.clear()
    headers_b = {"Authorization": f"Bearer {token_b}"}
    review = await client.post(
        "/access-reviews",
        headers=headers_b,
        json={
            "name": "Cross-tenant access review",
            "items": [{"system": "okta", "person_id": org_a_person}],
        },
    )
    assert review.status_code == 404

    create = await client.post(
        "/people",
        headers=headers_b,
        json={
            "full_name": "Grace Hopper",
            "email": f"p-{uuid.uuid4().hex[:8]}@example.com",
            "manager_id": org_a_person,
        },
    )
    assert create.status_code == 404

    org_b_person = await _person(client, headers_b)
    update = await client.patch(
        f"/people/{org_b_person}",
        headers=headers_b,
        json={"manager_id": org_a_person},
    )
    assert update.status_code == 404
