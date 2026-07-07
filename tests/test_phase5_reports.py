"""Phase 5A — audit-readiness reports, gaps, audit-package export, auditor scope."""

import io
import json
import uuid
import zipfile

import pytest
import refle_ai_core.config as ai_config
from conftest import db_available
from refle_ai_core.agents import register_builtin_agents
from refle_core.db import get_sessionmaker
from refle_core.security import create_access_token, hash_password
from refle_integrations.connectors import register_builtin_connectors

register_builtin_connectors()
register_builtin_agents()

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


@pytest.fixture(autouse=True)
def _offline_ai(monkeypatch):
    monkeypatch.setenv("REFLE_AI_PROVIDER", "local")
    monkeypatch.setenv("REFLE_AI_EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("REFLE_AI_LOCAL_BASE_URL", "http://localhost:9/v1")
    ai_config.get_ai_settings.cache_clear()
    yield
    ai_config.get_ai_settings.cache_clear()


async def _register(client) -> tuple[dict[str, str], uuid.UUID]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, uuid.UUID(data["organization_id"])


async def test_readiness_report(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)  # bootstrap

    report = (await client.get("/reports/readiness", headers=headers)).json()
    assert report["framework"]["total"] == 25
    assert report["framework"]["percent_ready"] == 0  # nothing assessed yet
    assert len(report["controls"]) == 25
    codes = {c["control_code"] for c in report["controls"]}
    assert "CC6.1" in codes


async def test_gaps_then_failing_after_sync(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)

    gaps = (await client.get("/reports/gaps", headers=headers)).json()
    kinds = {g["kind"] for g in gaps}
    assert "control_not_assessed" in kinds
    assert "no_evidence" in kinds
    assert "no_owner" in kinds

    # Demo sync flips CC6.1 to failing -> a high-severity failing gap appears.
    created = await client.post(
        "/connections", headers=headers, json={"provider": "demo", "label": "Demo"}
    )
    await client.post(f"/connections/{created.json()['id']}/sync", headers=headers)

    gaps2 = (await client.get("/reports/gaps", headers=headers)).json()
    failing = [g for g in gaps2 if g["kind"] == "control_failing"]
    assert any(g["control_code"] == "CC6.1" and g["severity"] == "high" for g in failing)


async def test_audit_package_is_valid_zip(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)

    resp = await client.get("/reports/audit-package", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = set(zf.namelist())
    assert {
        "manifest.json",
        "readiness_summary.md",
        "controls.json",
        "controls.md",
        "policies.md",
        "evidence_index.csv",
        "ssp_narrative.md",
    } <= names
    controls = json.loads(zf.read("controls.json"))
    assert len(controls) == 25
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["edition"] == "core"


async def test_auditor_is_read_only(client):
    headers, org_id = await _register(client)
    await client.get("/controls", headers=headers)
    policy = await client.post(
        "/policies",
        headers=headers,
        json={"name": "Security Policy", "body": "# security"},
    )
    assert policy.status_code == 201
    policy_id = policy.json()["id"]
    publish = await client.post(f"/policies/{policy_id}/versions/1/publish", headers=headers)
    assert publish.status_code == 200

    # Create an auditor membership + token directly.
    async with get_sessionmaker()() as session:
        from refle_core.models import Membership, Notification, Role, User

        u = User(
            email=f"aud-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("supersecret123"),
        )
        session.add(u)
        await session.flush()
        session.add(Membership(organization_id=org_id, user_id=u.id, role=Role.auditor))
        notification = Notification(
            organization_id=org_id,
            type="probe",
            title="Probe",
            body="Probe notification",
        )
        session.add(notification)
        await session.commit()
        token = create_access_token(str(u.id), extra={"org_id": str(org_id)})
        notification_id = notification.id

    aud = {"Authorization": f"Bearer {token}"}
    # Drop the owner's session cookie set during _register so the Bearer token
    # (auditor) is what authenticates — get_auth_context prefers the cookie.
    client.cookies.clear()

    # Auditor can read reports...
    assert (await client.get("/reports/readiness", headers=aud)).status_code == 200
    assert (await client.get("/reports/gaps", headers=aud)).status_code == 200
    # ...but cannot write (owner/admin only).
    create = await client.post(
        "/policies",
        headers=aud,
        json={"name": "X", "body": "# x"},
    )
    assert create.status_code == 403
    assert (await client.post(f"/policies/{policy_id}/accept", headers=aud)).status_code == 403
    assert (
        await client.post(f"/notifications/{notification_id}/read", headers=aud)
    ).status_code == 403
    assert (await client.get("/notifications/settings", headers=aud)).status_code == 403
