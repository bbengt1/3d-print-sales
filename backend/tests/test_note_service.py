from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.bill import Bill
from app.models.vendor import Vendor
from app.services.note_service import (
    NoteError,
    apply_credit_note,
    apply_debit_note,
    create_credit_note,
    create_debit_note,
    issue_credit_note,
    issue_debit_note,
    void_credit_note,
    void_debit_note,
)


async def _accounts(db_session) -> dict[str, Account]:
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


async def _customer(db_session) -> Customer:
    c = Customer(name="Test", email="x@y.z")
    db_session.add(c)
    await db_session.flush()
    return c


async def _vendor(db_session) -> Vendor:
    v = Vendor(name="Test Vendor")
    db_session.add(v)
    await db_session.flush()
    return v


async def _invoice(db_session, customer_id, total: Decimal) -> Invoice:
    inv = Invoice(
        invoice_number="INV-TEST-001",
        customer_id=customer_id,
        issue_date=datetime.date(2026, 5, 1),
        subtotal=total, total_due=total, balance_due=total,
        status="sent",
    )
    db_session.add(inv)
    await db_session.flush()
    return inv


# ---------- credit notes ----------


@pytest.mark.asyncio
async def test_create_credit_note_assigns_number(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "Refund", "quantity": "1", "unit_price": "50", "account_id": accts["4800"].id}],
    )
    assert n.credit_note_number.startswith("CN-")
    assert n.total_amount == Decimal("50.00")
    assert n.status == "draft"


@pytest.mark.asyncio
async def test_credit_note_no_lines_rejected(db_session):
    c = await _customer(db_session)
    with pytest.raises(NoteError):
        await create_credit_note(
            db_session,
            customer_id=c.id,
            issued_on=datetime.date(2026, 5, 1),
            lines=[],
        )


@pytest.mark.asyncio
async def test_issue_credit_note_posts_je(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "Refund", "quantity": "1", "unit_price": "50", "account_id": accts["4800"].id}],
    )
    n = await issue_credit_note(db_session, n.id)
    assert n.status == "issued"
    assert n.journal_entry_id is not None


@pytest.mark.asyncio
async def test_apply_credit_note_partially(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    inv = await _invoice(db_session, c.id, Decimal("200"))
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "Refund", "quantity": "1", "unit_price": "100", "account_id": accts["4800"].id}],
    )
    await issue_credit_note(db_session, n.id)
    app = await apply_credit_note(
        db_session, note_id=n.id, invoice_id=inv.id, amount=Decimal("60"),
    )
    assert Decimal(app.amount) == Decimal("60")
    refreshed = (await db_session.execute(select(type(n)).where(type(n).id == n.id))).scalar_one()
    assert Decimal(refreshed.applied_amount) == Decimal("60")
    assert refreshed.status == "partially_applied"
    # Invoice balance reduced
    inv2 = (await db_session.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert Decimal(inv2.balance_due) == Decimal("140")


@pytest.mark.asyncio
async def test_apply_overdraw_rejected(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    inv = await _invoice(db_session, c.id, Decimal("500"))
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "x", "quantity": "1", "unit_price": "50", "account_id": accts["4800"].id}],
    )
    await issue_credit_note(db_session, n.id)
    with pytest.raises(NoteError):
        await apply_credit_note(db_session, note_id=n.id, invoice_id=inv.id, amount=Decimal("100"))


@pytest.mark.asyncio
async def test_void_credit_note_blocked_after_application(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    inv = await _invoice(db_session, c.id, Decimal("100"))
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "x", "quantity": "1", "unit_price": "20", "account_id": accts["4800"].id}],
    )
    await issue_credit_note(db_session, n.id)
    await apply_credit_note(db_session, note_id=n.id, invoice_id=inv.id, amount=Decimal("20"))
    with pytest.raises(NoteError):
        await void_credit_note(db_session, n.id)


@pytest.mark.asyncio
async def test_void_credit_note_unapplied(db_session):
    accts = await _accounts(db_session)
    c = await _customer(db_session)
    n = await create_credit_note(
        db_session,
        customer_id=c.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "x", "quantity": "1", "unit_price": "10", "account_id": accts["4800"].id}],
    )
    await issue_credit_note(db_session, n.id)
    n = await void_credit_note(db_session, n.id)
    assert n.status == "void"


# ---------- debit notes ----------


@pytest.mark.asyncio
async def test_debit_note_lifecycle(db_session):
    accts = await _accounts(db_session)
    v = await _vendor(db_session)
    n = await create_debit_note(
        db_session,
        vendor_id=v.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "Return filament", "quantity": "1", "unit_price": "30", "account_id": accts["5400"].id}],
    )
    assert n.debit_note_number.startswith("DN-")
    n = await issue_debit_note(db_session, n.id)
    assert n.status == "issued"
    assert n.journal_entry_id is not None


@pytest.mark.asyncio
async def test_apply_debit_note(db_session):
    accts = await _accounts(db_session)
    v = await _vendor(db_session)
    accts2 = await _accounts(db_session)
    bill = Bill(
        bill_number="BL-1",
        vendor_id=v.id,
        account_id=accts2["6500"].id,
        description="Test bill",
        issue_date=datetime.date(2026, 5, 1),
        amount=Decimal("100"),
        status="open",
    )
    db_session.add(bill)
    await db_session.flush()

    n = await create_debit_note(
        db_session,
        vendor_id=v.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "Return", "quantity": "1", "unit_price": "30", "account_id": accts["5400"].id}],
    )
    await issue_debit_note(db_session, n.id)
    app = await apply_debit_note(db_session, note_id=n.id, bill_id=bill.id, amount=Decimal("30"))
    assert Decimal(app.amount) == Decimal("30")


@pytest.mark.asyncio
async def test_void_debit_note_unapplied(db_session):
    accts = await _accounts(db_session)
    v = await _vendor(db_session)
    n = await create_debit_note(
        db_session,
        vendor_id=v.id,
        issued_on=datetime.date(2026, 5, 1),
        lines=[{"description": "x", "quantity": "1", "unit_price": "10", "account_id": accts["5400"].id}],
    )
    await issue_debit_note(db_session, n.id)
    n = await void_debit_note(db_session, n.id)
    assert n.status == "void"
