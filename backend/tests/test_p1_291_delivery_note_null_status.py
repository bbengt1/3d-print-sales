"""Regression: PATCH /delivery-notes/{id} must reject ``{"status": null}``.

Codex P1 review on PR #291: ``DNUpdate`` permitted ``status: null`` and the
generic ``setattr`` update loop applied that value, but ``delivery_notes.status``
is non-nullable. The request would surface as a 500 IntegrityError at commit
time. Reject the null at the schema layer (422) instead.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.customer import Customer


async def _create_dn(client: AsyncClient, auth_headers, db_session) -> str:
    c = Customer(name="P1-291", email="p1-291@example.com")
    db_session.add(c)
    await db_session.commit()
    resp = await client.post(
        "/api/v1/delivery-notes",
        json={
            "customer_id": str(c.id),
            "issued_on": "2026-05-01",
            "lines": [{"description": "Widget", "quantity": "1"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_patch_with_null_status_returns_422(
    client: AsyncClient, auth_headers, db_session
):
    dn_id = await _create_dn(client, auth_headers, db_session)
    resp = await client.patch(
        f"/api/v1/delivery-notes/{dn_id}",
        json={"status": None},
        headers=auth_headers,
    )
    # Must be a client error (validation), not a 500 from the DB integrity
    # error that would otherwise occur at commit time.
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_patch_with_status_omitted_succeeds(
    client: AsyncClient, auth_headers, db_session
):
    dn_id = await _create_dn(client, auth_headers, db_session)
    resp = await client.patch(
        f"/api/v1/delivery-notes/{dn_id}",
        json={"tracking_number": "ABC123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["tracking_number"] == "ABC123"
    # status must remain at its prior (default) value, not be wiped to null.
    assert body["status"] == "draft"


@pytest.mark.asyncio
async def test_patch_with_valid_status_succeeds(
    client: AsyncClient, auth_headers, db_session
):
    dn_id = await _create_dn(client, auth_headers, db_session)
    resp = await client.patch(
        f"/api/v1/delivery-notes/{dn_id}",
        json={"status": "shipped"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "shipped"


@pytest.mark.asyncio
async def test_patch_with_empty_body_succeeds(
    client: AsyncClient, auth_headers, db_session
):
    dn_id = await _create_dn(client, auth_headers, db_session)
    resp = await client.patch(
        f"/api/v1/delivery-notes/{dn_id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "draft"
