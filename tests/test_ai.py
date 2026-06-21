"""RAG indexing + chat retrieval (offline HashEmbedder, requires Postgres+pgvector)."""

import uuid

import pytest
import refle_ai_core.config as ai_config
from conftest import db_available

pytestmark = pytest.mark.skipif(not db_available(), reason="requires Postgres on :5432")


@pytest.fixture(autouse=True)
def _offline_ai(monkeypatch):
    """Keep these tests offline/deterministic regardless of a local .env:
    hash embeddings (no key) and a local chat provider with no server (so chat
    deterministically falls back to retrieval-only). monkeypatch auto-restores."""
    monkeypatch.setenv("REFLE_AI_PROVIDER", "local")
    monkeypatch.setenv("REFLE_AI_EMBEDDING_PROVIDER", "hash")
    ai_config.get_ai_settings.cache_clear()
    yield
    ai_config.get_ai_settings.cache_clear()


async def _auth(client) -> dict[str, str]:
    email = f"u-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        "/auth/register",
        json={"org_name": "Co", "email": email, "password": "supersecret123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_status_uses_offline_embedder(client):
    headers = await _auth(client)
    status = (await client.get("/ai/status", headers=headers)).json()
    assert status["embedding_provider"] == "HashEmbedder"
    assert isinstance(status["model"], str) and status["model"]


async def test_reindex_then_chat_cites_relevant_control(client):
    headers = await _auth(client)
    await client.get("/controls", headers=headers)  # bootstrap org controls

    reindex = await client.post("/ai/reindex", headers=headers)
    assert reindex.status_code == 200
    assert reindex.json()["indexed"] >= 10

    chat = await client.post(
        "/ai/chat",
        headers=headers,
        json={"question": "What does logical access security require?"},
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["citations"], "expected retrieval citations"
    # The most relevant SOC 2 control should rank first.
    assert body["citations"][0]["source_id"] == "CC6.1"
    # No API key in tests -> retrieval-only fallback, but citations are real.
    assert body["generated"] is False


async def test_chat_autoindexes_when_empty(client):
    headers = await _auth(client)
    await client.get("/controls", headers=headers)
    chat = await client.post(
        "/ai/chat", headers=headers, json={"question": "change management process"}
    )
    assert chat.status_code == 200
    assert chat.json()["citations"][0]["source_id"] == "CC8.1"
