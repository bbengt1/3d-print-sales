"""#328 P2: division/project FKs across docs + report filtering."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.division import Division, Project
from app.models.invoice import Invoice
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import create_journal_entry
from app.services.report_service import generate_accrual_pl_report


async def _seed_revenue_pair(db_session):
    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one_or_none()
    if cash is None:
        cash = Account(code="1000", name="Cash", account_type="asset", normal_balance="debit")
        db_session.add(cash)
    rev = Account(code="4111", name="DivisionRev", account_type="revenue", normal_balance="credit")
    db_session.add(rev)
    await db_session.flush()
    return cash, rev


@pytest.mark.asyncio
async def test_invoice_persists_division_project(db_session):
    div = Division(name="West")
    proj = Project(name="Alpha")
    db_session.add_all([div, proj])
    await db_session.flush()
    inv = Invoice(
        invoice_number="INV-DIV-1",
        issue_date=datetime.date(2026, 5, 1),
        subtotal=Decimal("100"),
        tax_amount=Decimal("0"),
        shipping_amount=Decimal("0"),
        credits_applied=Decimal("0"),
        total_due=Decimal("100"),
        amount_paid=Decimal("0"),
        balance_due=Decimal("100"),
        division_id=div.id,
        project_id=proj.id,
        status="sent",
    )
    db_session.add(inv)
    await db_session.commit()
    refreshed = (await db_session.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert refreshed.division_id == div.id
    assert refreshed.project_id == proj.id


@pytest.mark.asyncio
async def test_pl_accrual_filtered_by_division(db_session):
    cash, rev = await _seed_revenue_pair(db_session)
    div_a = Division(name="DivA")
    div_b = Division(name="DivB")
    db_session.add_all([div_a, div_b])
    await db_session.flush()

    # Two JEs, different divisions, both posting to the same revenue account
    await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date=datetime.date(2026, 5, 1),
            memo="Sale A",
            division_id=div_a.id,
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("100")),
                JournalLineCreate(account_id=rev.id, entry_type="credit", amount=Decimal("100")),
            ],
        ),
    )
    await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date=datetime.date(2026, 5, 2),
            memo="Sale B",
            division_id=div_b.id,
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("250")),
                JournalLineCreate(account_id=rev.id, entry_type="credit", amount=Decimal("250")),
            ],
        ),
    )
    await db_session.commit()

    full = await generate_accrual_pl_report(db_session, datetime.date(2026, 5, 1), datetime.date(2026, 5, 31))
    only_a = await generate_accrual_pl_report(
        db_session, datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), division_id=div_a.id,
    )
    only_b = await generate_accrual_pl_report(
        db_session, datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), division_id=div_b.id,
    )
    assert full["revenue"]["total"] == Decimal("350")
    assert only_a["revenue"]["total"] == Decimal("100")
    assert only_b["revenue"]["total"] == Decimal("250")
