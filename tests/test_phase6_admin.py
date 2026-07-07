"""Tier 1 open-core admin: control scoping, audit log, and role gates."""

import uuid

import pytest
from conftest import db_available
from refle_core.db import get_sessionmaker

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


async def _register(client) -> tuple[dict[str, str], uuid.UUID]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, uuid.UUID(data["organization_id"])


async def test_scoping_excludes_from_posture_and_gaps(client):
    headers, _ = await _register(client)
    controls = (await client.get("/controls", headers=headers)).json()
    total_before = (await client.get("/controls/posture", headers=headers)).json()["total"]

    target = next(c for c in controls if c["control"]["code"] == "CC9.2")
    assert target["in_scope"] is True

    patched = await client.patch(
        f"/controls/{target['id']}", headers=headers, json={"in_scope": False}
    )
    assert patched.status_code == 200
    assert patched.json()["in_scope"] is False

    total_after = (await client.get("/controls/posture", headers=headers)).json()["total"]
    assert total_after == total_before - 1

    gaps = (await client.get("/reports/gaps", headers=headers)).json()
    assert all(g["control_code"] != "CC9.2" for g in gaps)


async def test_scope_and_status_changes_are_audited(client):
    headers, _ = await _register(client)
    controls = (await client.get("/controls", headers=headers)).json()
    cid = controls[0]["id"]

    await client.patch(f"/controls/{cid}", headers=headers, json={"status": "passing"})
    await client.patch(f"/controls/{cid}", headers=headers, json={"in_scope": False})

    log = (await client.get("/audit-log", headers=headers)).json()
    actions = {e["action"] for e in log}
    assert "control.status" in actions
    assert "control.scope" in actions


async def test_self_hosted_core_rejects_org_switching(client):
    headers, org_a = await _register(client)
    me = (await client.get("/auth/me", headers=headers)).json()
    user_id = uuid.UUID(me["id"])

    # Even if stale data contains another membership, Core stays single-org.
    async with get_sessionmaker()() as session:
        from refle_core.models import Membership, Organization, Role

        org_b = Organization(name="Second Co", slug=f"second-{uuid.uuid4().hex[:8]}")
        session.add(org_b)
        await session.flush()
        session.add(Membership(organization_id=org_b.id, user_id=user_id, role=Role.admin))
        await session.commit()
        org_b_id = org_b.id

    switched = await client.post(
        "/auth/switch-org", headers=headers, json={"organization_id": str(org_b_id)}
    )
    assert switched.status_code == 409

    # Re-selecting the active org is still harmless.
    same = await client.post(
        "/auth/switch-org", headers=headers, json={"organization_id": str(org_a)}
    )
    assert same.status_code == 200

    # Switching to an org the user doesn't belong to is also blocked by single-org mode.
    forbidden = await client.post(
        "/auth/switch-org", headers=headers, json={"organization_id": str(uuid.uuid4())}
    )
    assert forbidden.status_code == 409


async def test_audit_log_requires_owner_or_admin(client):
    from refle_core.security import create_access_token, hash_password

    headers, org_id = await _register(client)
    async with get_sessionmaker()() as session:
        from refle_core.models import Membership, Role, User

        u = User(
            email=f"m-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("supersecret123"),
        )
        session.add(u)
        await session.flush()
        session.add(Membership(organization_id=org_id, user_id=u.id, role=Role.member))
        await session.commit()
        token = create_access_token(str(u.id), extra={"org_id": str(org_id)})

    client.cookies.clear()  # avoid the owner cookie from _register
    member = {"Authorization": f"Bearer {token}"}
    assert (await client.get("/audit-log", headers=member)).status_code == 403
