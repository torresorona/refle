"""Integration tests for evidence + policies (require Postgres and MinIO)."""

import uuid

import pytest
from conftest import db_available

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


async def _auth(client) -> dict[str, str]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_evidence_upload_links_controls_and_downloads(client):
    headers = await _auth(client)
    controls = (await client.get("/controls", headers=headers)).json()
    ids = ",".join(c["id"] for c in controls[:2])

    payload = b"evidence-bytes"
    r = await client.post(
        "/evidence",
        headers=headers,
        data={"name": "Access Review", "control_ids": ids},
        files={"file": ("review.txt", payload, "text/plain")},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["size_bytes"] == len(payload)
    assert len(body["control_codes"]) == 2

    listing = (await client.get("/evidence", headers=headers)).json()
    assert len(listing) == 1

    dl = await client.get(f"/evidence/{listing[0]['id']}/download", headers=headers)
    assert dl.status_code == 200
    assert dl.json()["url"].startswith("http")


async def test_policy_versioning_and_acceptance(client):
    headers = await _auth(client)
    created = await client.post(
        "/policies", headers=headers, json={"name": "InfoSec Policy", "body": "v1"}
    )
    assert created.status_code == 201
    pid = created.json()["id"]

    accepted = await client.post(f"/policies/{pid}/accept", headers=headers)
    assert accepted.json()["accepted_by_me"] is True
    assert accepted.json()["accepted_count"] == 1

    v2 = await client.post(f"/policies/{pid}/versions", headers=headers, json={"body": "v2"})
    assert v2.json()["latest_version"] == 2
    # A new version must be re-accepted.
    assert v2.json()["accepted_by_me"] is False

    acceptances = await client.get(f"/policies/{pid}/acceptances", headers=headers)
    assert len(acceptances.json()) == 1
    assert acceptances.json()[0]["version"] == 1
