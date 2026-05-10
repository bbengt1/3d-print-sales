"""Phase 2 follow-ups: #261 conversion endpoints + #246 IAT edit."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.bill import Bill
from app.models.customer import Customer
from app.models.inter_account_transfer import InterAccountTransfer
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.journal_line import JournalLine
from app.models.vendor import Vendor
from app.services.bank_reconciliation_service import (
    finalize_reconciliation,
    include_line,
    start_reconciliation,
)
from app.services.inter_account_transfer_service import (
    InterAccountTransferError,
    create_inter_account_transfer,
    edit_inter_account_transfer,
)


# ---------- #261 P2 conversions ----------


@pytest.mark.asyncio
async def test_create_invoice_from_sales_order(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="Conv Test", email="c@x.com")
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
    so_id = create.json()["id"]
    await client.post(f"/api/v1/sales-orders/{so_id}/confirm", headers=auth_headers)

    resp = await client.post(
        f"/api/v1/sales-orders/{so_id}/create-invoice",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sales_order_id"] == so_id
    inv = (await db_session.execute(select(Invoice).where(Invoice.invoice_number == body["invoice_number"]))).scalar_one()
    lines = (await db_session.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))).scalars().all()
    assert len(lines) == 1
    assert Decimal(inv.total_due) == Decimal("50.00")
    assert "From sales order" in (inv.notes or "")


@pytest.mark.asyncio
async def test_create_invoice_from_draft_so_rejected(client: AsyncClient, auth_headers, db_session):
    c = Customer(name="Conv2", email="c2@x.com")
    db_session.add(c)
    await db_session.commit()
    create = await client.post(
        "/api/v1/sales-orders",
        json={
            "customer_id": str(c.id),
            "issue_date": "2026-05-01",
            "lines": [{"description": "X", "quantity": "1", "unit_price": "10"}],
        },
        headers=auth_headers,
    )
    so_id = create.json()["id"]
    # Don't confirm — try to invoice draft
    resp = await client.post(f"/api/v1/sales-orders/{so_id}/create-invoice", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_bill_from_purchase_order(client: AsyncClient, auth_headers, db_session):
    v = Vendor(name="POBill")
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
    po_id = create.json()["id"]
    await client.post(f"/api/v1/purchase-orders/{po_id}/confirm", headers=auth_headers)

    resp = await client.post(
        f"/api/v1/purchase-orders/{po_id}/create-bill",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    bill = (await db_session.execute(select(Bill).where(Bill.id == uuid_or_str(body["bill_id"])))).scalar_one()
    assert Decimal(bill.amount) == Decimal("200.00")
    assert bill.vendor_id == v.id


def uuid_or_str(s):
    import uuid
    return uuid.UUID(s)


# ---------- #246 P2 edit ----------


async def _bank(db_session, code, name) -> Account:
    a = Account(
        code=code, name=name, account_type="asset", normal_balance="debit",
        is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_edit_iat_replaces_je(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("500"),
        paid_on=datetime.date(2026, 5, 1),
    )
    old_je_id = t.journal_entry_id

    edited = await edit_inter_account_transfer(
        db_session, t.id, amount=Decimal("750"),
    )
    assert Decimal(edited.amount) == Decimal("750")
    assert edited.journal_entry_id != old_je_id
    # New JE has the new amount
    new_lines = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == edited.journal_entry_id)
        )
    ).scalars().all()
    assert len(new_lines) == 2
    assert all(Decimal(l.amount) == Decimal("750") for l in new_lines)


@pytest.mark.asyncio
async def test_edit_iat_blocked_when_leg_reconciled(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("100"),
        paid_on=datetime.date(2026, 5, 1),
    )
    src_line = (await db_session.execute(
        select(JournalLine).where(JournalLine.account_id == src.id).limit(1)
    )).scalar_one()
    recon = await start_reconciliation(
        db_session, account_id=src.id,
        statement_end_date=datetime.date(2026, 5, 31),
        statement_ending_balance=Decimal("-100"),
    )
    await include_line(db_session, reconciliation_id=recon.id, journal_line_id=src_line.id)
    await finalize_reconciliation(db_session, reconciliation_id=recon.id, finalized_by_user_id=None)

    with pytest.raises(InterAccountTransferError):
        await edit_inter_account_transfer(db_session, t.id, amount=Decimal("999"))


@pytest.mark.asyncio
async def test_edit_iat_can_change_dates(db_session):
    src = await _bank(db_session, "1010", "Operating")
    dst = await _bank(db_session, "1011", "Savings")
    t = await create_inter_account_transfer(
        db_session,
        from_account_id=src.id,
        to_account_id=dst.id,
        amount=Decimal("250"),
        paid_on=datetime.date(2026, 5, 1),
        received_on=datetime.date(2026, 5, 3),
    )
    edited = await edit_inter_account_transfer(
        db_session, t.id,
        paid_on=datetime.date(2026, 5, 10),
        received_on=datetime.date(2026, 5, 11),
    )
    assert edited.paid_on == datetime.date(2026, 5, 10)
    assert edited.received_on == datetime.date(2026, 5, 11)
    # Per-line posted_on dates updated on the new JE
    new_lines = (
        await db_session.execute(
            select(JournalLine)
            .where(JournalLine.journal_entry_id == edited.journal_entry_id)
            .order_by(JournalLine.line_number)
        )
    ).scalars().all()
    assert new_lines[0].posted_on == datetime.date(2026, 5, 10)
    assert new_lines[1].posted_on == datetime.date(2026, 5, 11)
