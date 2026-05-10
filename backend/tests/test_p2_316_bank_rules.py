"""#316 P2: bank-rule new actions, dry-run preview, create-rule-from-line."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.statement_import import StatementLine
from app.models.statement_match_rule import StatementMatchRule
from app.services.statement_import_service import import_statement
from app.services.statement_match_rule_service import (
    apply_rules_to_import,
    create_rule_from_line,
    preview_rules_for_import,
)


SAMPLE_CSV = """Date,Amount,Description,FITID
2026-05-01,-25.00,Filament supplier,FITID001
2026-05-03,500.00,Etsy payout,FITID002
"""


async def _bank(db_session, code="1010", name="Operating"):
    a = Account(
        code=code, name=name, account_type="asset", normal_balance="debit",
        is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _expense(db_session):
    a = Account(code="6555", name="Filament Expense", account_type="expense", normal_balance="debit")
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_create_journal_entry_action_posts_balanced_je(db_session):
    bank = await _bank(db_session)
    expense = await _expense(db_session)
    imp = await import_statement(
        db_session, account_id=bank.id, source_format="csv",
        source_filename="x.csv", content=SAMPLE_CSV.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Filament rule", account_id=bank.id,
        match_type="contains", match_pattern="Filament",
        match_amount_sign="debit",
        action="create_journal_entry",
        category_account_id=expense.id,
    ))
    await db_session.commit()

    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_journal_entries"] == 1

    matched_line = (
        await db_session.execute(
            select(StatementLine).where(StatementLine.import_id == imp.id, StatementLine.fitid == "FITID001")
        )
    ).scalar_one()
    assert matched_line.match_status == "matched"
    assert matched_line.matched_journal_line_id is not None

    # Verify the JE balanced
    bank_line = (
        await db_session.execute(select(JournalLine).where(JournalLine.id == matched_line.matched_journal_line_id))
    ).scalar_one()
    je_lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == bank_line.journal_entry_id))
    ).scalars().all()
    assert len(je_lines) == 2
    debits = sum(Decimal(l.amount) for l in je_lines if l.entry_type == "debit")
    credits = sum(Decimal(l.amount) for l in je_lines if l.entry_type == "credit")
    assert debits == credits == Decimal("25.00")


@pytest.mark.asyncio
async def test_dry_run_preview_does_not_mutate(db_session):
    bank = await _bank(db_session)
    expense = await _expense(db_session)
    imp = await import_statement(
        db_session, account_id=bank.id, source_format="csv",
        source_filename="x.csv", content=SAMPLE_CSV.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Filament", account_id=bank.id,
        match_type="contains", match_pattern="Filament",
        match_amount_sign="debit",
        action="create_journal_entry",
        category_account_id=expense.id,
    ))
    await db_session.commit()

    preview = await preview_rules_for_import(db_session, import_id=imp.id)
    assert preview["considered"] == 2
    assert preview["would_match"] == 1

    # No JE created, no line state change
    je_count = len((await db_session.execute(select(JournalEntry))).scalars().all())
    assert je_count == 0
    lines = (await db_session.execute(select(StatementLine).where(StatementLine.import_id == imp.id))).scalars().all()
    assert all(l.match_status == "unmatched" for l in lines)


@pytest.mark.asyncio
async def test_create_rule_from_line_seeds_pattern(db_session):
    bank = await _bank(db_session)
    expense = await _expense(db_session)
    imp = await import_statement(
        db_session, account_id=bank.id, source_format="csv",
        source_filename="x.csv", content=SAMPLE_CSV.encode(),
    )
    await db_session.commit()
    line = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "FITID001"))
    ).scalar_one()
    rule = await create_rule_from_line(
        db_session,
        statement_line_id=line.id,
        name="From-line rule",
        action="create_journal_entry",
        category_account_id=expense.id,
    )
    await db_session.commit()
    assert rule.match_amount_sign == "debit"
    assert "Filament" in rule.match_pattern or "supplier" in rule.match_pattern
    assert rule.action == "create_journal_entry"
    assert rule.category_account_id == expense.id
