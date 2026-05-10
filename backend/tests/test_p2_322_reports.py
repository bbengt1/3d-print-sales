"""#322 P2: AR-aging consolidation, P&L period comparison, account drill-down."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.services.report_service import (
    compute_ar_aging,
    compute_pl_comparison,
    drill_down_account,
)


@pytest.mark.asyncio
async def test_ar_aging_consolidated_endpoints_match(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="Aging", email="a@x.com")
    db_session.add(c)
    await db_session.commit()
    await client.post(
        "/api/v1/invoices",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-04-01",
            "due_date": "2026-04-15",
            "lines": [{"description": "X", "quantity": 1, "unit_price": "100"}],
        },
        headers=auth_headers,
    )
    r1 = await client.get("/api/v1/invoices/reports/ar-aging?as_of_date=2026-05-01", headers=auth_headers)
    r2 = await client.get("/api/v1/reports/ar-aging?as_of_date=2026-05-01", headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    # Both endpoints now share `compute_ar_aging` — totals must be identical.
    assert r1.json()["total_outstanding"] == r2.json()["total_outstanding"]
    assert r1.json()["bucket_1_30_total"] == r2.json()["bucket_1_30_total"]


@pytest.mark.asyncio
async def test_compute_ar_aging_buckets(db_session):
    c = Customer(name="Bk", email="b@x.com")
    db_session.add(c)
    await db_session.flush()
    from app.models.invoice import Invoice
    from app.models.invoice_line import InvoiceLine

    inv = Invoice(
        invoice_number="INV-001",
        customer_id=c.id,
        issue_date=datetime.date(2026, 4, 1),
        due_date=datetime.date(2026, 4, 1),
        subtotal=Decimal("100"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("100"),
        amount_paid=Decimal("0"),
        balance_due=Decimal("100"),
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(InvoiceLine(invoice_id=inv.id, description="X", quantity=1, unit_price=Decimal("100"), line_total=Decimal("100")))
    await db_session.commit()
    summary = await compute_ar_aging(db_session, datetime.date(2026, 5, 5))
    # 34 days past due → bucket_31_60
    assert Decimal(summary.bucket_31_60_total) == Decimal("100")


@pytest.mark.asyncio
async def test_pl_comparison_returns_both_periods(client: AsyncClient, auth_headers):
    r = await client.get(
        "/api/v1/reports/pl-comparison",
        params={
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "compare_to_start": "2026-03-01",
            "compare_to_end": "2026-03-31",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "current" in body and "prior" in body and "deltas" in body
    assert {"revenue_total", "cogs_total", "expenses_total", "gross_profit", "net_income"} <= set(body["deltas"].keys())


@pytest.mark.asyncio
async def test_drill_down_returns_lines_for_account(db_session):
    a = Account(code="9999", name="Test Drill", account_type="asset", normal_balance="debit")
    db_session.add(a)
    await db_session.flush()
    # No lines on this brand-new account
    payload = await drill_down_account(
        db_session, account_id=a.id, date_from=None, date_to=None,
    )
    assert payload["account_code"] == "9999"
    assert payload["rows"] == []
    assert Decimal(payload["net_change"]) == Decimal("0")


@pytest.mark.asyncio
async def test_drill_down_endpoint_smoke(client: AsyncClient, auth_headers, db_session):
    a = Account(code="9998", name="Smoke", account_type="asset", normal_balance="debit")
    db_session.add(a)
    await db_session.commit()
    r = await client.get(
        f"/api/v1/reports/account-drill-down?account_id={a.id}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["account_code"] == "9998"
