"""#331 P2: form templates CRUD."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.form_template import FormTemplate


@pytest.mark.asyncio
async def test_create_list_template(client: AsyncClient, auth_headers, db_session):
    r = await client.post(
        "/api/v1/form-templates",
        json={
            "scope": "invoice",
            "name": "Default invoice",
            "is_default": True,
            "defaults": {"due_in_days": 30, "notes": "Net 30"},
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["scope"] == "invoice"
    assert body["is_default"] is True
    assert body["defaults"]["due_in_days"] == 30

    lst = await client.get("/api/v1/form-templates/invoice", headers=auth_headers)
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_set_default_demotes_others(client: AsyncClient, auth_headers, db_session):
    db_session.add(FormTemplate(scope="quote", name="A", is_default=True, defaults={}))
    db_session.add(FormTemplate(scope="quote", name="B", is_default=False, defaults={}))
    await db_session.commit()
    rows = (await db_session.execute(select(FormTemplate).where(FormTemplate.scope == "quote"))).scalars().all()
    b_id = next(r.id for r in rows if r.name == "B")
    r = await client.patch(
        f"/api/v1/form-templates/{b_id}",
        json={"is_default": True},
        headers=auth_headers,
    )
    assert r.status_code == 200
    rows2 = (await db_session.execute(select(FormTemplate).where(FormTemplate.scope == "quote"))).scalars().all()
    defaults = [r.is_default for r in rows2]
    # Exactly one default after the swap
    assert sum(defaults) == 1


@pytest.mark.asyncio
async def test_unsupported_scope_400(client: AsyncClient, auth_headers):
    r = await client.get("/api/v1/form-templates/widget", headers=auth_headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_template(client: AsyncClient, auth_headers, db_session):
    t = FormTemplate(scope="bill", name="Bill default", defaults={})
    db_session.add(t)
    await db_session.commit()
    r = await client.delete(f"/api/v1/form-templates/{t.id}", headers=auth_headers)
    assert r.status_code == 204
    remaining = (await db_session.execute(select(FormTemplate).where(FormTemplate.id == t.id))).scalar_one_or_none()
    assert remaining is None
