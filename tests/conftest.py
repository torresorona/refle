"""Shared test fixtures."""

import socket

import httpx
import pytest
import refle_core.db as db
from refle_api.main import create_app


def db_available() -> bool:
    try:
        socket.create_connection(("localhost", 5432), timeout=0.5).close()
        return True
    except OSError:
        return False


@pytest.fixture(autouse=True)
async def _fresh_engine():
    """Each test runs in its own event loop; rebuild the async engine per test so
    asyncpg connections aren't reused across loops ('Event loop is closed')."""
    db._engine = None
    db._sessionmaker = None
    yield
    if db._engine is not None:
        await db._engine.dispose()
    db._engine = None
    db._sessionmaker = None


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
