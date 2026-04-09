"""Backend auth endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/api/v1/auth/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_register_new_user(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={
        "firebase_uid": "new-uid-123",
        "email": "newuser@example.com",
        "full_name": "New User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["onboarding_complete"] is False
    assert data["firebase_uid"] == "new-uid-123"


@pytest.mark.asyncio
async def test_register_idempotent(client: AsyncClient, registered_user):
    """Registering the same firebase_uid twice returns the existing user."""
    response = await client.post("/api/v1/auth/register", json={
        "firebase_uid": "test-firebase-uid",
        "email": "test@example.com",
        "full_name": "Test User",
    })
    assert response.status_code == 201
    assert response.json()["id"] == registered_user["id"]


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, registered_user):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["firebase_uid"] == "test-firebase-uid"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """Request without token returns 403 (no bearer scheme)."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_me_role(client: AsyncClient, registered_user):
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
        json={"role": "candidate"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "candidate"


@pytest.mark.asyncio
async def test_update_me_invalid_role(client: AsyncClient, registered_user):
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
        json={"role": "superadmin"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_me_candidate_profile(client: AsyncClient, registered_user):
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
        json={
            "role": "candidate",
            "headline": "Flutter Developer",
            "city": "Mumbai",
            "skill_tags": ["Flutter", "Dart", "Python"],
            "career_goal": "First Job",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["candidate_profile"]["headline"] == "Flutter Developer"
    assert data["candidate_profile"]["city"] == "Mumbai"
    assert "Flutter" in data["candidate_profile"]["skill_tags"]


@pytest.mark.asyncio
async def test_update_me_recruiter_profile(client: AsyncClient, registered_user):
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
        json={
            "role": "recruiter",
            "company_name": "TechCorp",
            "company_size": "51–200",
            "role_at_company": "Talent Lead",
            "hiring_domains": ["Engineering", "Design"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recruiter_profile"]["company_name"] == "TechCorp"
    assert "Engineering" in data["recruiter_profile"]["hiring_domains"]


@pytest.mark.asyncio
async def test_update_onboarding_complete(client: AsyncClient, registered_user):
    response = await client.put(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
        json={"onboarding_complete": True},
    )
    assert response.status_code == 200
    assert response.json()["onboarding_complete"] is True


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, registered_user):
    response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_account(client: AsyncClient, registered_user):
    response = await client.delete(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 204
    # Verify soft delete — user still exists but is_active = False
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert me_response.status_code == 403  # is_active=False blocks access
