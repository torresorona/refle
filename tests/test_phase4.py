"""Phase 4 — agentic AI: draft/publish workflow, AiRun audit, posture-change
notifications, dispatch, and policy templates.

All AI is pinned offline (local provider pointed at a closed port) so agents
deterministically hit their templated fallbacks and never touch a real API,
exactly like ``tests/test_ai.py``.
"""

import uuid

import pytest
import refle_ai_core.config as ai_config
from conftest import db_available
from refle_ai_core.agents import register_builtin_agents
from refle_core.db import get_sessionmaker
from refle_core.models import (
    AiRun,
    AiRunStatus,
    Control,
    ControlStatus,
    Notification,
    NotificationLevel,
    OrgControl,
)
from sqlalchemy import select

# ASGITransport doesn't run lifespan, so register agents explicitly for tests.
register_builtin_agents()

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


@pytest.fixture(autouse=True)
def _offline_ai(monkeypatch):
    """Force offline AI: a local provider pointed at a closed port (connection
    refused -> agents fall back) and hash embeddings (no key needed)."""
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
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return headers, uuid.UUID(data["organization_id"])


# --- draft / publish workflow ---


async def test_draft_policy_creates_draft_not_published(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)  # bootstrap org controls

    r = await client.post(
        "/ai/agents/draft-policy",
        headers=headers,
        json={"name": "Access Control Policy", "instructions": "Cover MFA."},
    )
    assert r.status_code == 201, r.text
    detail = r.json()
    assert detail["latest_version"] is None  # latest *published* is None
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["status"] == "draft"
    assert detail["versions"][0]["body"]  # templated fallback body is non-empty


async def test_draft_policy_records_succeeded_airun(client):
    headers, org_id = await _register(client)
    await client.get("/controls", headers=headers)
    r = await client.post(
        "/ai/agents/draft-policy", headers=headers, json={"name": "Vendor Mgmt"}
    )
    assert r.status_code == 201

    async with get_sessionmaker()() as session:
        runs = (
            (
                await session.execute(
                    select(AiRun).where(
                        AiRun.organization_id == org_id, AiRun.agent_key == "draft-policy"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(runs) == 1
    assert runs[0].status == AiRunStatus.succeeded
    assert runs[0].output  # fallback body persisted for audit


async def test_draft_from_template_uses_template_body(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)
    templates = (await client.get("/templates", headers=headers)).json()
    builtin = next(t for t in templates if t["type"] == "builtin")

    r = await client.post(
        "/ai/agents/draft-policy",
        headers=headers,
        json={"name": "AC", "template_id": builtin["id"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()["versions"][0]["body"]
    # Offline, the fallback returns the chosen template verbatim as the baseline.
    assert "Access Control Policy" in body


async def test_publish_then_accept_targets_published_version(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)
    draft = await client.post(
        "/ai/agents/draft-policy", headers=headers, json={"name": "Incident Response"}
    )
    pid = draft.json()["id"]

    # A draft-only policy cannot be accepted.
    acc = await client.post(f"/policies/{pid}/accept", headers=headers)
    assert acc.status_code == 400

    pub = await client.post(f"/policies/{pid}/versions/1/publish", headers=headers)
    assert pub.status_code == 200
    assert pub.json()["latest_version"] == 1
    assert pub.json()["versions"][0]["status"] == "published"

    acc2 = await client.post(f"/policies/{pid}/accept", headers=headers)
    assert acc2.status_code == 200
    assert acc2.json()["accepted_by_me"] is True
    assert acc2.json()["accepted_count"] == 1


async def test_only_drafts_are_editable(client):
    headers, _ = await _register(client)
    await client.get("/controls", headers=headers)
    draft = await client.post(
        "/ai/agents/draft-policy", headers=headers, json={"name": "Change Mgmt"}
    )
    pid = draft.json()["id"]

    # Editing a draft works.
    edit = await client.put(
        f"/policies/{pid}/versions/1", headers=headers, json={"body": "# Edited"}
    )
    assert edit.status_code == 200
    assert edit.json()["versions"][0]["body"] == "# Edited"

    # After publishing, the version is locked.
    await client.post(f"/policies/{pid}/versions/1/publish", headers=headers)
    locked = await client.put(
        f"/policies/{pid}/versions/1", headers=headers, json={"body": "# Nope"}
    )
    assert locked.status_code == 400


# --- posture-change detection + notifications ---


async def test_posture_flip_creates_one_notification_and_airun(client):
    headers, org_id = await _register(client)
    await client.get("/controls", headers=headers)  # bootstrap OrgControls

    from refle_integrations.engine import _apply_to_controls

    async with get_sessionmaker()() as session:
        oc = (
            await session.execute(
                select(OrgControl)
                .join(Control, OrgControl.control_id == Control.id)
                .where(OrgControl.organization_id == org_id, Control.code == "CC6.1")
            )
        ).scalar_one()
        oc.status = ControlStatus.passing  # establish a prior state to flip from
        await session.commit()

        failures, notifications = await _apply_to_controls(
            session, org_id, {"CC6.1": [False]}
        )
        await session.commit()

    assert failures == 1
    assert len(notifications) == 1
    assert notifications[0].level == NotificationLevel.warning

    # Visible through the API, and the posture-summary agent was audited.
    listed = (await client.get("/notifications", headers=headers)).json()
    assert len(listed) == 1
    assert listed[0]["level"] == "warning"

    async with get_sessionmaker()() as session:
        runs = (
            (
                await session.execute(
                    select(AiRun).where(
                        AiRun.organization_id == org_id,
                        AiRun.agent_key == "posture-summary",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(runs) == 1
    assert runs[0].status == AiRunStatus.succeeded


async def test_first_assessment_does_not_notify(client):
    """A control moving from not_assessed -> failing is an initial assessment,
    not a flip, so it should not raise a notification."""
    headers, org_id = await _register(client)
    await client.get("/controls", headers=headers)

    from refle_integrations.engine import _apply_to_controls

    async with get_sessionmaker()() as session:
        _, notifications = await _apply_to_controls(session, org_id, {"CC6.1": [False]})
        await session.commit()
    assert notifications == []

    listed = (await client.get("/notifications", headers=headers)).json()
    assert listed == []


async def test_mark_notification_read(client):
    headers, org_id = await _register(client)
    async with get_sessionmaker()() as session:
        n = Notification(
            organization_id=org_id,
            type="test",
            title="T",
            body="B",
            level=NotificationLevel.info,
        )
        session.add(n)
        await session.commit()

    listed = (await client.get("/notifications", headers=headers)).json()
    assert listed[0]["read_at"] is None
    nid = listed[0]["id"]

    read = await client.post(f"/notifications/{nid}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None


# --- notification settings + dispatch ---


async def test_clear_slack_webhook(client):
    headers, _ = await _register(client)
    s1 = await client.put(
        "/notifications/settings",
        headers=headers,
        json={"channels": "slack", "slack_webhook_url": "https://hooks.slack.com/x"},
    )
    assert s1.json()["slack_webhook_configured"] is True

    s2 = await client.put(
        "/notifications/settings", headers=headers, json={"slack_webhook_url": ""}
    )
    assert s2.json()["slack_webhook_configured"] is False


async def test_dispatch_unconfigured_is_noop(client):
    """No NotificationSetting for the org -> dispatch returns without error."""
    _, org_id = await _register(client)
    from refle_api.notify import dispatch_notifications

    async with get_sessionmaker()() as session:
        n = Notification(
            organization_id=org_id,
            type="test",
            title="T",
            body="B",
            level=NotificationLevel.info,
        )
        session.add(n)
        await session.commit()
        await session.refresh(n)
        await dispatch_notifications(session, [n])  # should not raise


async def test_dispatch_posts_to_slack_when_configured(client, monkeypatch):
    headers, org_id = await _register(client)
    await client.put(
        "/notifications/settings",
        headers=headers,
        json={"channels": "slack", "slack_webhook_url": "https://hooks.slack.com/abc"},
    )

    calls: list[tuple] = []

    class _FakeResp:
        def raise_for_status(self) -> None:
            pass

    async def _fake_post(self, url, **kwargs):  # noqa: ANN001 - test stub
        calls.append((url, kwargs))
        return _FakeResp()

    # Patch only after the test client is done making real ASGI calls.
    monkeypatch.setattr("httpx.AsyncClient.post", _fake_post)

    from refle_api.notify import dispatch_notifications

    async with get_sessionmaker()() as session:
        n = Notification(
            organization_id=org_id,
            type="posture_change",
            title="Posture Change",
            body="CC6.1 is failing",
            level=NotificationLevel.warning,
        )
        session.add(n)
        await session.commit()
        await session.refresh(n)
        await dispatch_notifications(session, [n])

    assert len(calls) == 1
    url, kwargs = calls[0]
    assert url == "https://hooks.slack.com/abc"  # decrypted webhook used
    assert "CC6.1 is failing" in kwargs["json"]["text"]


# --- templates ---


async def test_templates_list_includes_builtin_and_create_custom(client):
    headers, _ = await _register(client)
    templates = (await client.get("/templates", headers=headers)).json()
    assert any(t["type"] == "builtin" for t in templates)

    created = await client.post(
        "/templates",
        headers=headers,
        data={"name": "My Template", "body": "# Hello", "description": "d"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["type"] == "custom"
    assert created.json()["name"] == "My Template"
