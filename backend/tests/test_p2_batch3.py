"""Phase 2 batch 3:
- #258 P2: invoice tax_profile_id auto-computes tax_amount
- #261 P2: SO/PO auto-advance to fulfilled on conversion
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.purchase_order import PurchaseOrder
from app.models.sales_order import SalesOrder
from app.models.tax_profile import TaxProfile, TaxProfileComponent
from app.models.vendor import Vendor


# ---------- #258 P2 ----------


@pytest.mark.asyncio
async def test_invoice_create_with_tax_profile_auto_computes(client: AsyncClient, auth_headers, db_session):
    profile = TaxProfile(name="WA 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(profile)
    await db_session.commit()
    resp = await client.post(
        "/api/v1/invoices",
        json={
            "issue_date": "2026-05-01",
            "tax_amount": "0",
            "tax_profile_id": str(profile.id),
            "lines": [{"description": "Widget", "quantity": 5, "unit_price": "20"}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    # subtotal 100, tax 7%, so total_due = 107
    assert Decimal(body["tax_amount"]) == Decimal("7.00")


@pytest.mark.asyncio
async def test_invoice_explicit_tax_amount_overrides_profile(client: AsyncClient, auth_headers, db_session):
    profile = TaxProfile(name="WA 7%", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add(profile)
    await db_session.commit()
    resp = await client.post(
        "/api/v1/invoices",
        json={
            "issue_date": "2026-05-01",
            "tax_amount": "5",  # operator explicitly set
            "tax_profile_id": str(profile.id),
            "lines": [{"description": "Widget", "quantity": 5, "unit_price": "20"}],
        },
        headers=auth_headers,
    )
    body = resp.json()
    assert Decimal(body["tax_amount"]) == Decimal("5.00")


@pytest.mark.asyncio
async def test_invoice_compound_profile_auto_computes_total(client: AsyncClient, auth_headers, db_session):
    profile = TaxProfile(name="QC", jurisdiction="QC", tax_rate=Decimal("0"), is_compound=True)
    db_session.add(profile)
    await db_session.flush()
    db_session.add(TaxProfileComponent(profile_id=profile.id, name="GST", rate=Decimal("5.000"), apply_order=0))
    db_session.add(TaxProfileComponent(profile_id=profile.id, name="QST", rate=Decimal("9.975"), apply_order=1))
    await db_session.commit()
    resp = await client.post(
        "/api/v1/invoices",
        json={
            "issue_date": "2026-05-01",
            "tax_amount": "0",
            "tax_profile_id": str(profile.id),
            "lines": [{"description": "X", "quantity": 1, "unit_price": "100"}],
        },
        headers=auth_headers,
    )
    body = resp.json()
    # 5% + (9.975% on 105) = 5 + 10.47 = 15.47
    assert Decimal(body["tax_amount"]) == Decimal("15.47")


# ---------- #261 P2 fulfillment ----------


@pytest.mark.asyncio
async def test_so_auto_advances_to_fulfilled(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="FulfilC", email="f@u.l")
    db_session.add(c)
    await db_session.commit()
    create = await client.post(
        "/api/v1/sales-orders",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "Widget", "quantity": "5", "unit_price": "10"}],
        },
        headers=auth_headers,
    )
    import uuid
    so_id = uuid.UUID(create.json()["id"])
    await client.post(f"/api/v1/sales-orders/{so_id}/confirm", headers=auth_headers)
    await client.post(f"/api/v1/sales-orders/{so_id}/create-invoice", headers=auth_headers)
    db_session.expire_all()
    so = (await db_session.execute(select(SalesOrder).where(SalesOrder.id == so_id))).scalar_one()
    assert so.status == "fulfilled"


@pytest.mark.asyncio
async def test_po_auto_advances_to_fulfilled(client: AsyncClient, auth_headers, db_session):
    v = Vendor(name="FulfilV")
    db_session.add(v)
    await db_session.commit()
    create = await client.post(
        "/api/v1/purchase-orders",
        json={
            "vendor_id": str(v.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "Filament", "quantity": "10", "unit_price": "20"}],
        },
        headers=auth_headers,
    )
    import uuid
    po_id = uuid.UUID(create.json()["id"])
    await client.post(f"/api/v1/purchase-orders/{po_id}/confirm", headers=auth_headers)
    await client.post(f"/api/v1/purchase-orders/{po_id}/create-bill", headers=auth_headers)
    db_session.expire_all()
    po = (await db_session.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id))).scalar_one()
    assert po.status == "fulfilled"
