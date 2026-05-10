"""#327 P2: batch CSV import + undo."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.customer import Customer


@pytest.mark.asyncio
async def test_csv_import_creates_customers(client: AsyncClient, auth_headers, db_session):
    csv = (
        "name,email,phone\n"
        "Alice,a@x.com,555-1\n"
        "Bob,b@x.com,555-2\n"
    ).encode()
    r = await client.post(
        "/api/v1/batch/customer/import.csv",
        files={"file": ("c.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2
    assert body["skipped"] == 0
    rows = (await db_session.execute(select(Customer))).scalars().all()
    names = {c.name for c in rows}
    assert {"Alice", "Bob"} <= names


@pytest.mark.asyncio
async def test_csv_import_skips_existing_by_name(client: AsyncClient, auth_headers, db_session):
    db_session.add(Customer(name="Carol", email="old@x.x"))
    await db_session.commit()
    csv = (
        "name,email\n"
        "Carol,new@x.com\n"
        "Dan,d@x.com\n"
    ).encode()
    r = await client.post(
        "/api/v1/batch/customer/import.csv",
        files={"file": ("c.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    body = r.json()
    assert body["created"] == 1
    assert body["skipped"] == 1
    # Carol's email unchanged
    carol = (await db_session.execute(select(Customer).where(Customer.name == "Carol"))).scalar_one()
    assert carol.email == "old@x.x"


@pytest.mark.asyncio
async def test_undo_batch_removes_imports(client: AsyncClient, auth_headers, db_session):
    csv = "name,email\nEd,e@x.com\nFay,f@x.com\n".encode()
    r = await client.post(
        "/api/v1/batch/customer/import.csv",
        files={"file": ("c.csv", csv, "text/csv")},
        headers=auth_headers,
    )
    batch_id = r.json()["batch_id"]
    assert (await db_session.execute(select(Customer).where(Customer.name.in_(["Ed", "Fay"])))).scalars().all()
    u = await client.post(
        f"/api/v1/batch/sessions/{batch_id}/undo",
        headers=auth_headers,
    )
    assert u.status_code == 200
    assert u.json()["deleted"] == 2
    leftover = (await db_session.execute(select(Customer).where(Customer.name.in_(["Ed", "Fay"])))).scalars().all()
    assert leftover == []
    # Audit log carries the undo tombstone
    tomb = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "batch_csv_undo", AuditLog.entity_id == batch_id)
        )
    ).scalar_one()
    assert tomb.after_snapshot["deleted"] == 2


@pytest.mark.asyncio
async def test_undo_unknown_batch_404(client: AsyncClient, auth_headers):
    import uuid

    r = await client.post(f"/api/v1/batch/sessions/{uuid.uuid4()}/undo", headers=auth_headers)
    assert r.status_code == 404
