"""Shared test fixtures."""

import socket

import httpx
import pytest
import refle_core.db as db
from refle_api.main import create_app
from refle_core.models import Base, PolicyTemplate
from sqlalchemy import delete


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
    if db_available():
        await _reset_app_data()
    yield
    if db._engine is not None:
        await db._engine.dispose()
    db._engine = None
    db._sessionmaker = None


async def _reset_app_data() -> None:
    """Clear instance-owned rows while preserving the seeded control catalog."""
    async with db.get_sessionmaker()() as session:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in {"frameworks", "controls"}:
                continue
            if table.name == "policy_templates":
                await session.execute(
                    delete(PolicyTemplate).where(PolicyTemplate.organization_id.is_not(None))
                )
                continue
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
