from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.services.accounting_service import ensure_accounting_period, seed_chart_of_accounts


@pytest.mark.asyncio
async def test_locked_period_blocks_sale_update_and_delete(client, auth_headers, db_session: AsyncSession, seed_material):
    await seed_chart_of_accounts(db_session)
    await ensure_accounting_period(
        db_session,
        period_key="2026-06",
        name="June 2026",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
        status="locked",
    )

    product = Product(sku="CTRL-001", name="Locked Widget", material_id=seed_material.id, stock_qty=10, reorder_point=2)
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    sale_resp = await client.post(
        "/api/v1/sales",
        headers=auth_headers,
        json={
            "date": "2026-06-15",
            "customer_name": "Locked Customer",
            "status": "paid",
            "items": [{"product_id": str(product.id), "description": "Locked Widget", "quantity": 1, "unit_price": 20.0, "unit_cost": 8.0}],
        },
    )
    assert sale_resp.status_code == 201
    sale = sale_resp.json()

    update_resp = await client.put(f"/api/v1/sales/{sale['id']}", headers=auth_headers, json={"notes": "should fail"})
    assert update_resp.status_code == 400
    assert "locked accounting period" in update_resp.json()["detail"].lower()

    delete_resp = await client.delete(f"/api/v1/sales/{sale['id']}", headers=auth_headers)
    assert delete_resp.status_code == 400
    assert "locked accounting period" in delete_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_locked_period_blocks_invoice_delete(client, auth_headers):
    invoice_resp = await client.post(
        "/api/v1/invoices",
        headers=auth_headers,
        json={
            "invoice_number": "INV-LOCK-1",
            "issue_date": "2026-07-10",
            "due_date": "2026-07-20",
            "customer_name": "Locked Invoice Customer",
            "status": "sent",
            "lines": [{"description": "Widget", "quantity": 1, "unit_price": "25.00"}],
        },
    )
    assert invoice_resp.status_code == 201
    invoice = invoice_resp.json()

    # lock the period after the record exists
    period_resp = await client.post(
        "/api/v1/accounting/periods",
        headers=auth_headers,
        json={
            "period_key": "2026-07",
            "name": "July 2026",
            "start_date": "2026-07-01",
            "end_date": "2026-07-31",
            "status": "open",
            "is_adjustment_period": False,
        },
    )
    period = period_resp.json()
    await client.post(f"/api/v1/accounting/periods/{period['id']}/status", headers=auth_headers, json={"status": "locked"})

    delete_resp = await client.delete(f"/api/v1/invoices/{invoice['id']}", headers=auth_headers)
    assert delete_resp.status_code == 400
    assert "locked accounting period" in delete_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_posted_journal_entry_still_corrected_by_reversal_not_edit(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-08",
        name="August 2026",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        status="open",
    )
    accounts = (await client.get('/api/v1/accounting/accounts', headers=auth_headers)).json()
    cash = next(a for a in accounts if a['code'] == '1000')
    equity = next(a for a in accounts if a['code'] == '3000')

    entry_resp = await client.post(
        "/api/v1/accounting/journal-entries",
        headers=auth_headers,
        json={
            "entry_date": "2026-08-05",
            "accounting_period_id": str(period.id),
            "memo": "Posted entry",
            "lines": [
                {"account_id": cash['id'], "entry_type": "debit", "amount": "100.00"},
                {"account_id": equity['id'], "entry_type": "credit", "amount": "100.00"},
            ],
        },
    )
    assert entry_resp.status_code == 201
    entry = entry_resp.json()

    reverse_resp = await client.post(
        f"/api/v1/accounting/journal-entries/{entry['id']}/reverse",
        headers=auth_headers,
        json={"reversal_date": "2026-08-06", "memo": "Correction reversal"},
    )
    assert reverse_resp.status_code == 201
    assert reverse_resp.json()["is_reversal"] is True
