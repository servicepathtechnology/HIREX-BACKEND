"""Pytest fixtures for HireX backend tests."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import patch, MagicMock

from app.main import app
from app.core.database import Base, get_db

# Use SQLite in-memory for tests (no Postgres needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async test client with DB override and Firebase mocked."""
    app.dependency_overrides[get_db] = override_get_db

    mock_decoded = {"uid": "test-firebase-uid", "email": "test@example.com"}

    with patch("app.core.firebase.auth.verify_id_token", return_value=mock_decoded):
        with patch("app.core.firebase.init_firebase"):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client):
    """Creates and returns a registered user."""
    response = await client.post("/api/v1/auth/register", json={
        "firebase_uid": "test-firebase-uid",
        "email": "test@example.com",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    return response.json()
