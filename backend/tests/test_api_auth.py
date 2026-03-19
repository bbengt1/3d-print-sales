from __future__ import annotations

import pytest

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_login_success(client, db_session):
    user = User(
        email="login@example.com",
        hashed_password=hash_password("secret123"),
        full_name="Login User",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client, db_session):
    user = User(
        email="badpw@example.com",
        hashed_password=hash_password("correct"),
        full_name="Bad PW User",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "badpw@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_email(client):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "anything"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_deactivated_user(client, db_session):
    user = User(
        email="inactive@example.com",
        hashed_password=hash_password("pass"),
        full_name="Inactive",
        role="admin",
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "pass"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_authenticated(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client, auth_headers):
    resp = await client.put(
        "/api/v1/auth/me/password",
        json={"current_password": "testpass", "new_password": "newpass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Login with new password
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "newpass123"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, auth_headers):
    resp = await client.put(
        "/api/v1/auth/me/password",
        json={"current_password": "wrong", "new_password": "newpass123"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# --- Admin user management ---


@pytest.mark.asyncio
async def test_register_user(client, auth_headers):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "secure123",
            "full_name": "New User",
            "role": "user",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "user"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_register_duplicate_email(client, auth_headers):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "secure123",
            "full_name": "Dup User",
        },
        headers=auth_headers,
    )
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": "secure123",
            "full_name": "Dup User 2",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_requires_admin(client, user_headers):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "blocked@example.com",
            "password": "secure123",
            "full_name": "Blocked",
        },
        headers=user_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_users(client, auth_headers):
    resp = await client.get("/api/v1/auth/users", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_list_users_requires_admin(client, user_headers):
    resp = await client.get("/api/v1/auth/users", headers=user_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_user(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "getme@example.com",
            "password": "secure123",
            "full_name": "Get Me",
        },
        headers=auth_headers,
    )
    uid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/auth/users/{uid}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "getme@example.com"


@pytest.mark.asyncio
async def test_update_user(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "upd@example.com",
            "password": "secure123",
            "full_name": "Update Me",
        },
        headers=auth_headers,
    )
    uid = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/auth/users/{uid}",
        json={"full_name": "Updated Name", "role": "admin"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Name"
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    uid = me.json()["id"]

    resp = await client.put(
        f"/api/v1/auth/users/{uid}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(client, auth_headers):
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    uid = me.json()["id"]

    resp = await client.put(
        f"/api/v1/auth/users/{uid}",
        json={"role": "user"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_deactivate_user(client, auth_headers):
    create_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "deact@example.com",
            "password": "secure123",
            "full_name": "Deactivate Me",
        },
        headers=auth_headers,
    )
    uid = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/auth/users/{uid}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify deactivated
    resp = await client.get(f"/api/v1/auth/users/{uid}", headers=auth_headers)
    assert resp.json()["is_active"] is False

    # Verify can't login
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "deact@example.com", "password": "secure123"},
    )
    assert resp.status_code == 403
