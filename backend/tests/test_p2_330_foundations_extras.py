"""#330 P2: starting-balances CSV import + suspense reclassify."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import create_journal_entry


async def _ensure_obe_and_account(db_session, code, name, account_type, normal_balance):
    obe = (await db_session.execute(select(Account).where(Account.code == "3300"))).scalar_one_or_none()
    if obe is None:
        db_session.add(Account(code="3300", name="Opening Balance Equity", account_type="equity", normal_balance="credit"))
    a = Account(code=code, name=name, account_type=account_type, normal_balance=normal_balance)
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_starting_balances_csv_happy_path(client: AsyncClient, auth_headers, db_session):
    a = await _ensure_obe_and_account(db_session, "1099", "Test Asset", "asset", "debit")
    await db_session.commit()
    csv = "account_code,amount\n1099,1500\n".encode()
    files = {"file": ("sb.csv", csv, "text/csv")}
    r = await client.post(
        "/api/v1/accounting/starting-balances.csv?as_of=2026-01-01",
        files=files,
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_processed"] == 1
    je = (await db_session.execute(select(JournalEntry).where(JournalEntry.id == uuid.UUID(body["journal_entry_id"])))).scalar_one()
    lines = (await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == je.id))).scalars().all()
    # One line on the asset, one on OBE
    assert len(lines) == 2
    assert sum(Decimal(l.amount) for l in lines if l.entry_type == "debit") == Decimal("1500")
    assert sum(Decimal(l.amount) for l in lines if l.entry_type == "credit") == Decimal("1500")


@pytest.mark.asyncio
async def test_starting_balances_csv_missing_columns(client: AsyncClient, auth_headers):
    csv = "foo,bar\nx,y\n".encode()
    files = {"file": ("sb.csv", csv, "text/csv")}
    r = await client.post(
        "/api/v1/accounting/starting-balances.csv?as_of=2026-01-01",
        files=files,
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_starting_balances_csv_unknown_code(client: AsyncClient, auth_headers, db_session):
    csv = "account_code,amount\nZZ-NOPE,100\n".encode()
    files = {"file": ("sb.csv", csv, "text/csv")}
    r = await client.post(
        "/api/v1/accounting/starting-balances.csv?as_of=2026-01-01",
        files=files,
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "Unknown account codes" in r.json()["detail"]


@pytest.mark.asyncio
async def test_suspense_reclassify_posts_balanced_je(client: AsyncClient, auth_headers, db_session):
    # Make sure 1900 exists
    suspense = (await db_session.execute(select(Account).where(Account.code == "1900"))).scalar_one_or_none()
    if suspense is None:
        suspense = Account(code="1900", name="Suspense", account_type="asset", normal_balance="debit")
        db_session.add(suspense)
        await db_session.flush()
    # Create a target expense account
    expense = Account(code="6999", name="Misc Expense", account_type="expense", normal_balance="debit")
    db_session.add(expense)
    # Create a counterparty for the original suspense JE (cash)
    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one_or_none()
    if cash is None:
        cash = Account(code="1000", name="Cash", account_type="asset", normal_balance="debit")
        db_session.add(cash)
    await db_session.flush()
    # Post: Dr Suspense 50, Cr Cash 50 → suspense holds the unknown
    je = await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date="2026-04-15",
            memo="Unknown bank deposit",
            lines=[
                JournalLineCreate(account_id=suspense.id, entry_type="debit", amount=Decimal("50")),
                JournalLineCreate(account_id=cash.id, entry_type="credit", amount=Decimal("50")),
            ],
        ),
    )
    await db_session.commit()
    suspense_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == je.id, JournalLine.account_id == suspense.id)
        )
    ).scalar_one()

    r = await client.post(
        "/api/v1/accounting/suspense/reclassify",
        json={
            "journal_line_id": str(suspense_line.id),
            "target_account_id": str(expense.id),
            "posted_on": "2026-04-20",
            "description": "Bank fee — reclassified",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    new_je_id = r.json()["journal_entry_id"]
    new_lines = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == uuid.UUID(new_je_id))
        )
    ).scalars().all()
    assert len(new_lines) == 2
    # Suspense line now offset (credit), expense debited
    sides = {(l.account_id, l.entry_type): Decimal(l.amount) for l in new_lines}
    assert sides[(suspense.id, "credit")] == Decimal("50")
    assert sides[(expense.id, "debit")] == Decimal("50")


@pytest.mark.asyncio
async def test_suspense_reclassify_refuses_non_suspense_line(client: AsyncClient, auth_headers, db_session):
    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one_or_none()
    if cash is None:
        cash = Account(code="1000", name="Cash", account_type="asset", normal_balance="debit")
        db_session.add(cash)
    rev = Account(code="4001", name="Rev", account_type="revenue", normal_balance="credit")
    db_session.add(rev)
    await db_session.flush()
    je = await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date="2026-04-15",
            memo="Sale",
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("10")),
                JournalLineCreate(account_id=rev.id, entry_type="credit", amount=Decimal("10")),
            ],
        ),
    )
    await db_session.commit()
    cash_line = (
        await db_session.execute(
            select(JournalLine).where(JournalLine.journal_entry_id == je.id, JournalLine.account_id == cash.id)
        )
    ).scalar_one()
    r = await client.post(
        "/api/v1/accounting/suspense/reclassify",
        json={
            "journal_line_id": str(cash_line.id),
            "target_account_id": str(rev.id),
            "posted_on": "2026-04-20",
        },
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "Suspense" in r.json()["detail"]
