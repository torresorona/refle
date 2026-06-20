"""API smoke tests via ASGI transport (no network, no DB needed)."""

import httpx
from refle_api.main import create_app


async def test_health():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_meta_reports_gateway_and_license():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/meta")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "refle"
    assert data["ai"]["model"] == "gemini-3.5-flash"
    assert data["license"]["tier"] == "oss"
    assert data["connectors"] == []
