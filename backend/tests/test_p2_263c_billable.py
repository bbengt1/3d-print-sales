"""#263 P2: billable expenses."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.billable_expense import BillableExpense
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine


async def _customer_invoice(db_session) -> tuple[Customer, Invoice]:
    c = Customer(name="Bill Cust", email="b@x.x")
    db_session.add(c)
    await db_session.flush()
    inv = Invoice(
        invoice_number="INV-BE-1",
        customer_id=c.id,
        customer_name=c.name,
        issue_date=datetime.date(2026, 5, 1),
        due_date=datetime.date(2026, 5, 31),
        subtotal=Decimal("100"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("100"),
        amount_paid=Decimal("0"),
        balance_due=Decimal("100"),
        status="draft",
    )
    db_session.add(inv)
    await db_session.flush()
    return c, inv


@pytest.mark.asyncio
async def test_create_billable_expense(client: AsyncClient, auth_headers, db_session):
    c, _ = await _customer_invoice(db_session)
    await db_session.commit()
    r = await client.post(
        "/api/v1/billable-expenses",
        json={
            "customer_id": str(c.id),
            "description": "Subcontractor",
            "cost": "200",
            "markup_pct": "10",
            "incurred_on": "2026-04-15",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    # 200 * 1.10 = 220
    assert Decimal(body["rebillable_amount"]) == Decimal("220.00")


@pytest.mark.asyncio
async def test_add_to_invoice_appends_line(client: AsyncClient, auth_headers, db_session):
    c, inv = await _customer_invoice(db_session)
    inv_id = inv.id
    be = BillableExpense(
        customer_id=c.id, description="Travel", cost=Decimal("50"),
        markup_pct=Decimal("0"), incurred_on=datetime.date(2026, 4, 15),
    )
    db_session.add(be)
    await db_session.flush()
    be_id = be.id
    await db_session.commit()

    r = await client.post(
        f"/api/v1/billable-expenses/{be_id}/add-to-invoice",
        json={"invoice_id": str(inv_id)},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "invoiced"
    db_session.expire_all()
    refreshed_inv = (await db_session.execute(select(Invoice).where(Invoice.id == inv_id))).scalar_one()
    assert Decimal(refreshed_inv.subtotal) == Decimal("150")
    assert Decimal(refreshed_inv.total_due) == Decimal("150")
    assert Decimal(refreshed_inv.balance_due) == Decimal("150")
    lines = (await db_session.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv_id))).scalars().all()
    assert any("Pass-through" in l.description for l in lines)


@pytest.mark.asyncio
async def test_void_pending(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="V", email="v@x.x")
    db_session.add(c)
    await db_session.flush()
    be = BillableExpense(
        customer_id=c.id, description="X", cost=Decimal("10"),
        markup_pct=Decimal("0"), incurred_on=datetime.date(2026, 4, 15),
    )
    db_session.add(be)
    await db_session.flush()
    be_id = be.id
    await db_session.commit()
    r = await client.post(f"/api/v1/billable-expenses/{be_id}/void", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "voided"


@pytest.mark.asyncio
async def test_cannot_rebill_invoiced(client: AsyncClient, auth_headers, db_session):
    c, inv = await _customer_invoice(db_session)
    be = BillableExpense(
        customer_id=c.id, description="X", cost=Decimal("10"),
        markup_pct=Decimal("0"), incurred_on=datetime.date(2026, 4, 15),
        status="invoiced", invoice_id=inv.id,
    )
    db_session.add(be)
    await db_session.flush()
    be_id = be.id
    inv_id = inv.id
    await db_session.commit()
    r = await client.post(
        f"/api/v1/billable-expenses/{be_id}/add-to-invoice",
        json={"invoice_id": str(inv_id)},
        headers=auth_headers,
    )
    assert r.status_code == 400
