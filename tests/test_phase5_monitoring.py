"""Phase 5B — posture trend snapshots + per-connection monitoring schedule."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from conftest import db_available
from refle_core.models import Connection
from refle_integrations.connectors import register_builtin_connectors
from refle_integrations.engine import is_due

# ASGITransport doesn't run lifespan; register connectors for the sync tests.
register_builtin_connectors()


def _conn(**kw) -> Connection:
    c = Connection()
    c.monitoring_enabled = kw.get("monitoring_enabled", True)
    c.last_synced_at = kw.get("last_synced_at")
    c.sync_interval_minutes = kw.get("sync_interval_minutes")
    return c


def test_is_due_predicate():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert is_due(_conn(monitoring_enabled=False), now) is False
    assert is_due(_conn(last_synced_at=None), now) is True
    # No per-connection interval -> the global schedule decides; always eligible.
    recent = now - timedelta(minutes=5)
    assert is_due(_conn(last_synced_at=recent, sync_interval_minutes=None), now) is True
    # Interval not yet elapsed -> not due.
    assert is_due(_conn(last_synced_at=recent, sync_interval_minutes=60), now) is False
    # Interval elapsed -> due.
    old = now - timedelta(minutes=90)
    assert is_due(_conn(last_synced_at=old, sync_interval_minutes=60), now) is True


pytestmark_db = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


async def _auth(client) -> dict[str, str]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytestmark_db
async def test_sync_records_posture_snapshot(client):
    headers = await _auth(client)
    await client.get("/controls", headers=headers)
    created = await client.post(
        "/connections", headers=headers, json={"provider": "demo", "label": "Demo"}
    )
    cid = created.json()["id"]
    # New connections default to monitoring enabled, global schedule.
    assert created.json()["monitoring_enabled"] is True
    assert created.json()["sync_interval_minutes"] is None

    await client.post(f"/connections/{cid}/sync", headers=headers)

    history = (await client.get("/controls/posture/history", headers=headers)).json()
    assert len(history) >= 1
    latest = history[-1]
    assert latest["passing"] + latest["failing"] + latest["not_assessed"] > 0
    assert 0 <= latest["percent_ready"] <= 100


@pytestmark_db
async def test_update_connection_monitoring(client):
    headers = await _auth(client)
    created = await client.post(
        "/connections", headers=headers, json={"provider": "demo", "label": "Demo"}
    )
    cid = created.json()["id"]

    patched = await client.patch(
        f"/connections/{cid}",
        headers=headers,
        json={"monitoring_enabled": False, "sync_interval_minutes": 120},
    )
    assert patched.status_code == 200
    assert patched.json()["monitoring_enabled"] is False
    assert patched.json()["sync_interval_minutes"] == 120
