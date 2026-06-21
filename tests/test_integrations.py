"""Connector test functions (pure) + the sync engine end-to-end (via API)."""

import uuid

import pytest
from conftest import db_available
from refle_integrations.base import Resource
from refle_integrations.connectors import register_builtin_connectors
from refle_integrations.connectors.aws import iam_mfa, s3_public

# ASGITransport doesn't run lifespan, so register connectors explicitly for tests.
register_builtin_connectors()

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


def test_aws_iam_mfa_pure_function():
    mixed = [
        Resource("iam_user", "a", {"mfa_enabled": True}),
        Resource("iam_user", "b", {"mfa_enabled": False}),
    ]
    assert iam_mfa(mixed).passed is False
    assert iam_mfa([Resource("iam_user", "a", {"mfa_enabled": True})]).passed is True


def test_aws_s3_public_pure_function():
    assert s3_public([Resource("s3_bucket", "x", {"public": True})]).passed is False
    assert s3_public([Resource("s3_bucket", "x", {"public": False})]).passed is True


async def _auth(client) -> dict[str, str]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_connector_catalog(client):
    headers = await _auth(client)
    catalog = (await client.get("/integrations/connectors", headers=headers)).json()
    keys = {c["key"] for c in catalog}
    assert {"demo", "aws", "github", "okta"} <= keys


async def test_demo_sync_drives_posture_and_remediation(client):
    headers = await _auth(client)
    await client.get("/controls", headers=headers)  # bootstrap org controls

    created = await client.post(
        "/connections", headers=headers, json={"provider": "demo", "label": "Demo"}
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    sync = await client.post(f"/connections/{cid}/sync", headers=headers)
    assert sync.status_code == 200
    body = sync.json()
    assert body["ok"] is True
    assert body["tests_run"] == 4
    assert body["failures"] == 1

    posture = (await client.get("/controls/posture", headers=headers)).json()
    assert posture["passing"] == 3
    assert posture["failing"] == 1

    results = (await client.get(f"/connections/{cid}/results", headers=headers)).json()
    assert len(results) == 4

    tasks = (await client.get("/remediation-tasks", headers=headers)).json()
    assert any(t["control_code"] == "CC6.1" for t in tasks)


async def test_unknown_provider_rejected(client):
    headers = await _auth(client)
    r = await client.post("/connections", headers=headers, json={"provider": "nope", "label": "x"})
    assert r.status_code == 404
