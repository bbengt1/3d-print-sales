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
