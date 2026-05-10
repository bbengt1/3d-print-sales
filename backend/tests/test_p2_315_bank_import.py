"""#315 P2: QFX format + persisted CSV mapping + create-tx-from-line."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.bank_import_mapping import BankImportMapping
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.statement_import import StatementLine
from app.services.statement_import_service import (
    StatementImportError,
    create_transaction_from_line,
    import_statement,
)


SAMPLE_QFX = """OFXHEADER:100
DATA:OFXSGML

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260501
<TRNAMT>-15.00
<FITID>QFX001
<NAME>Coffee shop
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260503
<TRNAMT>250.00
<FITID>QFX002
<NAME>Refund
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


# Bank statement uses the bank's column conventions (e.g. "Posted Date", "Memo")
SAMPLE_CSV_CUSTOM = (
    "Posted Date,Memo,Debit,Credit,Reference\n"
    "2026-05-01,Coffee shop,-15.00,,REF1\n"
    "2026-05-03,Refund,,250.00,REF2\n"
)


async def _bank(db_session, code="1010"):
    a = Account(
        code=code, name="Operating",
        account_type="asset", normal_balance="debit",
        is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_qfx_format_accepted(db_session):
    a = await _bank(db_session)
    await db_session.commit()
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="qfx",
        source_filename="export.qfx",
        content=SAMPLE_QFX.encode(),
    )
    assert imp.line_count == 2
    rows = (await db_session.execute(select(StatementLine))).scalars().all()
    fitids = sorted(r.fitid for r in rows)
    assert fitids == ["QFX001", "QFX002"]


@pytest.mark.asyncio
async def test_unknown_format_rejected(db_session):
    a = await _bank(db_session)
    await db_session.commit()
    with pytest.raises(StatementImportError, match="Unsupported"):
        await import_statement(
            db_session,
            account_id=a.id,
            source_format="json",
            source_filename="x.json",
            content=b"{}",
        )


@pytest.mark.asyncio
async def test_persisted_mapping_used_when_no_override(db_session):
    """Operator saves a mapping for this account, then a CSV import that
    doesn't pass a mapping should pick up the saved one."""
    a = await _bank(db_session)
    db_session.add(
        BankImportMapping(
            account_id=a.id,
            mapping={
                "date": "Posted Date",
                "amount": "Debit",  # negative amount column
                "description": "Memo",
                "fitid": "Reference",
            },
        )
    )
    await db_session.commit()

    # The default parser would look for "Date","Amount" — without a mapping it
    # would parse 0 rows from this CSV. With the persisted mapping it picks
    # up the negative debits.
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="csv",
        source_filename="bank.csv",
        content=SAMPLE_CSV_CUSTOM.encode(),
    )
    # Only the row with a non-empty Debit will parse since amount→Debit
    assert imp.line_count == 1
    line = (await db_session.execute(select(StatementLine))).scalar_one()
    assert line.fitid == "REF1"
    assert Decimal(line.amount) == Decimal("-15.00")


@pytest.mark.asyncio
async def test_caller_override_beats_persisted_mapping(db_session):
    a = await _bank(db_session)
    db_session.add(
        BankImportMapping(
            account_id=a.id,
            mapping={"date": "WRONG", "amount": "WRONG", "description": "WRONG", "fitid": "WRONG"},
        )
    )
    await db_session.commit()
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="csv",
        source_filename="bank.csv",
        content=SAMPLE_CSV_CUSTOM.encode(),
        csv_mapping_override={
            "date": "Posted Date",
            "amount": "Credit",
            "description": "Memo",
            "fitid": "Reference",
        },
    )
    assert imp.line_count == 1
    line = (await db_session.execute(select(StatementLine))).scalar_one()
    assert line.fitid == "REF2"


@pytest.mark.asyncio
async def test_create_transaction_from_line_inflow(db_session):
    """A positive-amount line clears with Dr bank / Cr target."""
    a = await _bank(db_session)
    rev = Account(code="4111", name="Misc Income", account_type="revenue", normal_balance="credit")
    db_session.add(rev)
    await db_session.commit()
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="qfx",
        source_filename="x.qfx",
        content=SAMPLE_QFX.encode(),
    )
    inflow = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "QFX002"))
    ).scalar_one()
    inflow_id = inflow.id
    a_id = a.id
    rev_id = rev.id

    res = await create_transaction_from_line(
        db_session, statement_line_id=inflow_id, target_account_id=rev_id,
    )
    assert res["direction"] == "inflow"

    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "statement_import_create_tx")
        )
    ).scalar_one()
    lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == je.id))
    ).scalars().all()
    sides = {(l.account_id, l.entry_type): Decimal(l.amount) for l in lines}
    assert sides[(a_id, "debit")] == Decimal("250.00")
    assert sides[(rev_id, "credit")] == Decimal("250.00")
    refreshed_line = (
        await db_session.execute(select(StatementLine).where(StatementLine.id == inflow_id))
    ).scalar_one()
    assert refreshed_line.match_status == "matched"
    assert refreshed_line.matched_journal_line_id is not None


@pytest.mark.asyncio
async def test_create_transaction_outflow_flips_sides(db_session):
    a = await _bank(db_session)
    exp = Account(code="6555", name="Misc Expense", account_type="expense", normal_balance="debit")
    db_session.add(exp)
    await db_session.commit()
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="qfx",
        source_filename="x.qfx",
        content=SAMPLE_QFX.encode(),
    )
    outflow = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "QFX001"))
    ).scalar_one()
    res = await create_transaction_from_line(
        db_session, statement_line_id=outflow.id, target_account_id=exp.id,
    )
    assert res["direction"] == "outflow"
    je = (
        await db_session.execute(
            select(JournalEntry).where(JournalEntry.source_type == "statement_import_create_tx")
        )
    ).scalar_one()
    lines = (
        await db_session.execute(select(JournalLine).where(JournalLine.journal_entry_id == je.id))
    ).scalars().all()
    sides = {(l.account_id, l.entry_type): Decimal(l.amount) for l in lines}
    assert sides[(a.id, "credit")] == Decimal("15.00")
    assert sides[(exp.id, "debit")] == Decimal("15.00")


@pytest.mark.asyncio
async def test_create_transaction_refuses_already_matched(db_session):
    a = await _bank(db_session)
    exp = Account(code="6555", name="Misc Expense", account_type="expense", normal_balance="debit")
    db_session.add(exp)
    await db_session.commit()
    await import_statement(
        db_session, account_id=a.id, source_format="qfx",
        source_filename="x.qfx", content=SAMPLE_QFX.encode(),
    )
    line = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "QFX001"))
    ).scalar_one()
    line.match_status = "ignored"
    await db_session.flush()
    with pytest.raises(StatementImportError, match="status ignored"):
        await create_transaction_from_line(
            db_session, statement_line_id=line.id, target_account_id=exp.id,
        )
