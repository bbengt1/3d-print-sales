from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.statement_import import StatementImport, StatementLine
from app.services.statement_import_service import (
    StatementImportError,
    ignore_line,
    import_statement,
    match_line,
    parse_csv,
    parse_ofx,
    suggest_matches,
)


SAMPLE_OFX = """
OFXHEADER:100
DATA:OFXSGML

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260501
<TRNAMT>-25.00
<FITID>FITID001
<NAME>Filament supplier
<MEMO>monthly bulk
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260503
<TRNAMT>500.00
<FITID>FITID002
<NAME>Etsy payout
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


SAMPLE_CSV = """Date,Amount,Description,FITID
2026-05-01,-25.00,Filament supplier,FITID001
2026-05-03,500.00,Etsy payout,FITID002
"""


def test_parse_ofx_extracts_two_rows():
    rows = parse_ofx(SAMPLE_OFX)
    assert len(rows) == 2
    assert rows[0]["posted_date"] == datetime.date(2026, 5, 1)
    assert rows[0]["amount"] == Decimal("-25.00")
    assert rows[0]["fitid"] == "FITID001"
    assert "Filament" in rows[0]["description"] or "monthly" in rows[0]["description"]
    assert rows[1]["amount"] == Decimal("500.00")


def test_parse_csv_basic():
    rows = parse_csv(SAMPLE_CSV)
    assert len(rows) == 2
    assert rows[0]["amount"] == Decimal("-25.00")
    assert rows[0]["fitid"] == "FITID001"


async def _bank(db_session, code="1010", name="Operating"):
    a = Account(
        code=code,
        name=name,
        account_type="asset",
        normal_balance="debit",
        is_bank_account=True,
        bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest.mark.asyncio
async def test_import_ofx_persists_lines(db_session):
    a = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    await db_session.commit()
    assert imp.line_count == 2
    assert imp.duplicate_count == 0
    rows = (await db_session.execute(select(StatementLine))).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_import_dedupes_by_fitid(db_session):
    a = await _bank(db_session)
    await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    imp2 = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    await db_session.commit()
    assert imp2.line_count == 0
    assert imp2.duplicate_count == 2


@pytest.mark.asyncio
async def test_import_rejects_non_bank_account(db_session):
    a = Account(code="9999", name="Misc", account_type="liability", normal_balance="credit", is_bank_account=False)
    db_session.add(a)
    await db_session.flush()
    with pytest.raises(StatementImportError):
        await import_statement(
            db_session,
            account_id=a.id,
            source_format="ofx",
            source_filename="x.ofx",
            content=SAMPLE_OFX.encode(),
        )


@pytest.mark.asyncio
async def test_match_line_promotes_journal_line_to_cleared(db_session):
    a = await _bank(db_session)
    # Create a JE on this account that matches one of the statement lines
    je = JournalEntry(entry_number="JE-1", entry_date=datetime.date(2026, 5, 1), status="posted")
    db_session.add(je)
    await db_session.flush()
    jl = JournalLine(
        journal_entry_id=je.id,
        account_id=a.id,
        line_number=1,
        entry_type="credit",
        amount=Decimal("25.00"),  # matches abs(-25.00) from the OFX
    )
    db_session.add(jl)
    await db_session.flush()

    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    sl = (await db_session.execute(
        select(StatementLine).where(StatementLine.import_id == imp.id, StatementLine.fitid == "FITID001")
    )).scalar_one()

    suggestions = await suggest_matches(db_session, statement_line_id=sl.id)
    assert len(suggestions) >= 1
    assert suggestions[0].id == jl.id

    matched = await match_line(db_session, statement_line_id=sl.id, journal_line_id=jl.id)
    await db_session.commit()
    assert matched.match_status == "matched"
    refreshed_jl = (await db_session.execute(select(JournalLine).where(JournalLine.id == jl.id))).scalar_one()
    assert refreshed_jl.cleared_status == "cleared"


@pytest.mark.asyncio
async def test_ignore_line_marks_status(db_session):
    a = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    sl = (await db_session.execute(
        select(StatementLine).where(StatementLine.import_id == imp.id).limit(1)
    )).scalar_one()
    sl = await ignore_line(db_session, sl.id)
    await db_session.commit()
    assert sl.match_status == "ignored"


@pytest.mark.asyncio
async def test_match_rejects_already_matched(db_session):
    a = await _bank(db_session)
    je = JournalEntry(entry_number="JE-1", entry_date=datetime.date(2026, 5, 1), status="posted")
    db_session.add(je)
    await db_session.flush()
    jl = JournalLine(
        journal_entry_id=je.id,
        account_id=a.id,
        line_number=1,
        entry_type="credit",
        amount=Decimal("25.00"),
    )
    db_session.add(jl)
    await db_session.flush()

    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="export.ofx",
        content=SAMPLE_OFX.encode(),
    )
    sl = (await db_session.execute(
        select(StatementLine).where(StatementLine.import_id == imp.id, StatementLine.fitid == "FITID001")
    )).scalar_one()
    await match_line(db_session, statement_line_id=sl.id, journal_line_id=jl.id)
    with pytest.raises(StatementImportError):
        await match_line(db_session, statement_line_id=sl.id, journal_line_id=jl.id)
