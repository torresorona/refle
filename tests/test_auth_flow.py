"""Integration tests for auth + controls (require Postgres on :5432)."""

import uuid

import pytest
from conftest import db_available

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


async def test_register_me_and_owner_role(client):
    email = _unique_email()
    r = await client.post(
        "/auth/register",
        json={"org_name": "Test Co", "email": email, "password": "supersecret123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "owner"

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert len(me.json()["memberships"]) == 1


async def test_controls_bootstrap_patch_and_posture(client):
    headers = await _register(client)

    controls = (await client.get("/controls", headers=headers)).json()
    assert len(controls) >= 1  # bootstrapped from the seeded catalog

    cid = controls[0]["id"]
    patched = await client.patch(f"/controls/{cid}", headers=headers, json={"status": "passing"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "passing"

    posture = (await client.get("/controls/posture", headers=headers)).json()
    assert posture["passing"] >= 1
    assert posture["total"] == len(controls)


async def test_login_and_invitation(client):
    email = _unique_email()
    await client.post(
        "/auth/register",
        json={"org_name": "Inv Co", "email": email, "password": "supersecret123"},
    )
    login = await client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    invite = await client.post(
        "/auth/invitations",
        headers=headers,
        json={"email": _unique_email(), "role": "admin"},
    )
    assert invite.status_code == 201
    assert invite.json()["status"] == "pending"


async def test_auth_required_and_bad_credentials(client):
    assert (await client.get("/controls")).status_code == 401
    assert (await client.get("/auth/me", headers={"Authorization": "Bearer x"})).status_code == 401
    bad = await client.post("/auth/login", json={"email": _unique_email(), "password": "whatever"})
    assert bad.status_code == 401


async def test_member_can_read_but_not_edit_controls(client):
    owner = await _register(client)
    member_email = _unique_email()
    invite = await client.post(
        "/auth/invitations", headers=owner, json={"email": member_email, "role": "member"}
    )
    token = invite.json()["token"]
    accepted = await client.post(
        "/auth/accept-invite", json={"token": token, "password": "supersecret123"}
    )
    assert accepted.status_code == 200
    member = {"Authorization": f"Bearer {accepted.json()['access_token']}"}

    controls = (await client.get("/controls", headers=member)).json()
    assert len(controls) >= 1  # members can read
    forbidden = await client.patch(
        f"/controls/{controls[0]['id']}", headers=member, json={"status": "passing"}
    )
    assert forbidden.status_code == 403  # but cannot edit


async def _register(client) -> dict[str, str]:
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": _unique_email(), "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
