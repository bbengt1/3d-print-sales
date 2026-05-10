"""#326 P2: custom-field hard delete + value search."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.custom_field import CustomFieldDefinition, CustomFieldValue


async def _create_def(db_session, scope="customer", key="loyalty", field_type="string"):
    d = CustomFieldDefinition(scope=scope, key=key, name=key.title(), field_type=field_type)
    db_session.add(d)
    await db_session.flush()
    return d


@pytest.mark.asyncio
async def test_hard_delete_refuses_when_values_exist(client: AsyncClient, auth_headers, db_session):
    d = await _create_def(db_session)
    import uuid as _u
    db_session.add(CustomFieldValue(definition_id=d.id, record_id=_u.uuid4(), value="gold"))
    await db_session.commit()
    r = await client.delete(f"/api/v1/custom-fields/{d.id}/hard", headers=auth_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_hard_delete_with_force_removes_all(client: AsyncClient, auth_headers, db_session):
    d = await _create_def(db_session, key="loyalty2")
    import uuid as _u
    db_session.add(CustomFieldValue(definition_id=d.id, record_id=_u.uuid4(), value="silver"))
    await db_session.commit()
    r = await client.delete(f"/api/v1/custom-fields/{d.id}/hard?force=true", headers=auth_headers)
    assert r.status_code == 204
    remaining = (await db_session.execute(select(CustomFieldDefinition).where(CustomFieldDefinition.id == d.id))).scalar_one_or_none()
    assert remaining is None


@pytest.mark.asyncio
async def test_value_search_returns_matching_records(client: AsyncClient, auth_headers, db_session):
    d = await _create_def(db_session, key="tier")
    import uuid as _u
    a = _u.uuid4()
    b = _u.uuid4()
    c = _u.uuid4()
    db_session.add_all([
        CustomFieldValue(definition_id=d.id, record_id=a, value="gold"),
        CustomFieldValue(definition_id=d.id, record_id=b, value="silver"),
        CustomFieldValue(definition_id=d.id, record_id=c, value="gold"),
    ])
    await db_session.commit()
    r = await client.get(
        "/api/v1/custom-fields/values/customer/search?key=tier&value=gold",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["match_count"] == 2
    assert set(body["record_ids"]) == {str(a), str(c)}


@pytest.mark.asyncio
async def test_value_search_unknown_field_404(client: AsyncClient, auth_headers, db_session):
    r = await client.get(
        "/api/v1/custom-fields/values/customer/search?key=nope&value=foo",
        headers=auth_headers,
    )
    assert r.status_code == 404
