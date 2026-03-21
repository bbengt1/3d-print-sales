from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.journal_entry import JournalEntry
from app.services.accounting_service import (
    AccountingValidationError,
    create_journal_entry,
    ensure_accounting_period,
    reverse_journal_entry,
    seed_chart_of_accounts,
)
from app.schemas.accounting import JournalEntryCreate, JournalEntryReverse, JournalLineCreate


@pytest.mark.asyncio
async def test_seed_chart_of_accounts(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)

    result = await db_session.execute(select(Account).order_by(Account.code))
    accounts = result.scalars().all()

    assert len(accounts) >= 20
    assert any(a.code == "1000" and a.name == "Cash" for a in accounts)
    assert any(a.code == "4000" and a.name == "Product Sales" for a in accounts)
    assert any(a.code == "5000" and a.name == "Material COGS" for a in accounts)


@pytest.mark.asyncio
async def test_seed_chart_of_accounts_is_idempotent(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    first_count = len((await db_session.execute(select(Account))).scalars().all())

    await seed_chart_of_accounts(db_session)
    second_count = len((await db_session.execute(select(Account))).scalars().all())

    assert first_count == second_count


@pytest.mark.asyncio
async def test_ensure_accounting_period(db_session: AsyncSession):
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    assert period.period_key == "2026-03"
    assert period.status == "open"

    again = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    assert again.id == period.id


@pytest.mark.asyncio
async def test_create_balanced_journal_entry(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    sales = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()

    entry = await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date=date(2026, 3, 21),
            accounting_period_id=period.id,
            source_type="sale",
            source_id="S-2026-0001",
            memo="Record direct sale",
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("25.00")),
                JournalLineCreate(account_id=sales.id, entry_type="credit", amount=Decimal("25.00")),
            ],
        ),
    )

    assert entry.status == "posted"
    assert len(entry.lines) == 2
    assert entry.entry_number.startswith("JE-2026-")

    saved = (await db_session.execute(select(JournalEntry))).scalars().all()
    assert len(saved) == 1


@pytest.mark.asyncio
async def test_unbalanced_journal_entry_is_rejected(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    sales = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()

    with pytest.raises(AccountingValidationError, match="unbalanced"):
        await create_journal_entry(
            db_session,
            JournalEntryCreate(
                entry_date=date(2026, 3, 21),
                accounting_period_id=period.id,
                lines=[
                    JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("30.00")),
                    JournalLineCreate(account_id=sales.id, entry_type="credit", amount=Decimal("25.00")),
                ],
            ),
        )


@pytest.mark.asyncio
async def test_closed_period_journal_entry_is_rejected(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = AccountingPeriod(
        period_key="2026-02",
        name="February 2026",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
        status="closed",
    )
    db_session.add(period)
    await db_session.commit()
    await db_session.refresh(period)

    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    sales = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()

    with pytest.raises(AccountingValidationError, match="non-open accounting period"):
        await create_journal_entry(
            db_session,
            JournalEntryCreate(
                entry_date=date(2026, 2, 20),
                accounting_period_id=period.id,
                lines=[
                    JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("25.00")),
                    JournalLineCreate(account_id=sales.id, entry_type="credit", amount=Decimal("25.00")),
                ],
            ),
        )


@pytest.mark.asyncio
async def test_reverse_posted_journal_entry(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    sales = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()

    entry = await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date=date(2026, 3, 21),
            accounting_period_id=period.id,
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("25.00")),
                JournalLineCreate(account_id=sales.id, entry_type="credit", amount=Decimal("25.00")),
            ],
        ),
    )

    reversal = await reverse_journal_entry(
        db_session,
        entry_id=entry.id,
        payload=JournalEntryReverse(reversal_date=date(2026, 3, 22), memo="Reverse mistaken entry"),
    )

    assert reversal.is_reversal is True
    assert reversal.reversal_of_id == entry.id
    assert len(reversal.lines) == 2
    assert reversal.lines[0].entry_type == "credit"
    assert reversal.lines[1].entry_type == "debit"


@pytest.mark.asyncio
async def test_cannot_reverse_entry_twice(db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )

    cash = (await db_session.execute(select(Account).where(Account.code == "1000"))).scalar_one()
    sales = (await db_session.execute(select(Account).where(Account.code == "4000"))).scalar_one()

    entry = await create_journal_entry(
        db_session,
        JournalEntryCreate(
            entry_date=date(2026, 3, 21),
            accounting_period_id=period.id,
            lines=[
                JournalLineCreate(account_id=cash.id, entry_type="debit", amount=Decimal("25.00")),
                JournalLineCreate(account_id=sales.id, entry_type="credit", amount=Decimal("25.00")),
            ],
        ),
    )
    await reverse_journal_entry(
        db_session,
        entry_id=entry.id,
        payload=JournalEntryReverse(reversal_date=date(2026, 3, 22)),
    )

    with pytest.raises(AccountingValidationError, match="already been reversed"):
        await reverse_journal_entry(
            db_session,
            entry_id=entry.id,
            payload=JournalEntryReverse(reversal_date=date(2026, 3, 23)),
        )
