"""Regression tests for Codex P1 review on PR #280.

Two integrity holes in the statement-import match flow:

1. `match_line` never checked whether the target `journal_line_id` was
   already claimed by another `StatementLine`. Operators could attach
   the same journal line to multiple statement rows; all would flip to
   `matched` even though only one accounting line exists, hiding
   un-reconciled activity.

2. `ignore_line` only flipped `match_status` to `ignored`. If the row
   had previously been matched, the FK to the journal line and the
   journal line's promoted `cleared` state both stayed in place, so
   the worksheet kept treating the wrong journal line as cleared.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.statement_import import StatementLine
from app.services.statement_import_service import (
    StatementImportError,
    ignore_line,
    import_statement,
    match_line,
)


# Two CREDIT lines for the SAME amount on the SAME account, so a single
# journal line is a plausible match for either statement row.
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
<FITID>FIT-A
<NAME>Filament supplier
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260501
<TRNAMT>-25.00
<FITID>FIT-B
<NAME>Filament supplier (second)
</STMTTRN>
</BANKTRANLIST>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""


async def _bank(db_session) -> Account:
    a = Account(
        code="1010",
        name="Operating",
        account_type="asset",
        normal_balance="debit",
        is_bank_account=True,
        bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


async def _journal_line(db_session, account: Account, amount: Decimal) -> JournalLine:
    je = JournalEntry(
        entry_number=f"JE-{amount}",
        entry_date=datetime.date(2026, 5, 1),
        status="posted",
    )
    db_session.add(je)
    await db_session.flush()
    jl = JournalLine(
        journal_entry_id=je.id,
        account_id=account.id,
        line_number=1,
        entry_type="credit",
        amount=amount,
    )
    db_session.add(jl)
    await db_session.flush()
    return jl


@pytest.mark.asyncio
async def test_match_rejects_journal_line_already_used_by_another_statement_line(
    db_session,
):
    """P1 #280: a single journal line cannot back two statement rows."""
    a = await _bank(db_session)
    jl = await _journal_line(db_session, a, Decimal("25.00"))

    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="dup.ofx",
        content=SAMPLE_OFX.encode(),
    )
    rows = (
        await db_session.execute(
            select(StatementLine)
            .where(StatementLine.import_id == imp.id)
            .order_by(StatementLine.fitid)
        )
    ).scalars().all()
    assert len(rows) == 2
    line_a, line_b = rows[0], rows[1]

    # First match succeeds.
    await match_line(db_session, statement_line_id=line_a.id, journal_line_id=jl.id)

    # Second match against the same journal line must be rejected.
    with pytest.raises(StatementImportError) as exc:
        await match_line(
            db_session, statement_line_id=line_b.id, journal_line_id=jl.id
        )
    assert "already matched" in str(exc.value).lower()

    # And line B must remain unmatched after the rejected attempt.
    refreshed_b = (
        await db_session.execute(
            select(StatementLine).where(StatementLine.id == line_b.id)
        )
    ).scalar_one()
    assert refreshed_b.match_status == "unmatched"
    assert refreshed_b.matched_journal_line_id is None


@pytest.mark.asyncio
async def test_ignore_after_match_clears_linkage_and_reverts_cleared_state(db_session):
    """P1 #280: ignoring a matched line must roll back the prior match."""
    a = await _bank(db_session)
    jl = await _journal_line(db_session, a, Decimal("25.00"))

    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="dup.ofx",
        content=SAMPLE_OFX.encode(),
    )
    line_a = (
        await db_session.execute(
            select(StatementLine).where(
                StatementLine.import_id == imp.id,
                StatementLine.fitid == "FIT-A",
            )
        )
    ).scalar_one()

    matched = await match_line(
        db_session, statement_line_id=line_a.id, journal_line_id=jl.id
    )
    assert matched.match_status == "matched"
    assert matched.matched_journal_line_id == jl.id
    refreshed_jl = (
        await db_session.execute(select(JournalLine).where(JournalLine.id == jl.id))
    ).scalar_one()
    assert refreshed_jl.cleared_status == "cleared"

    # Now ignore the previously-matched line.
    ignored = await ignore_line(db_session, line_a.id)
    assert ignored.match_status == "ignored"
    assert ignored.matched_journal_line_id is None

    refreshed_jl = (
        await db_session.execute(select(JournalLine).where(JournalLine.id == jl.id))
    ).scalar_one()
    # Journal line must lose its `cleared` promotion so the worksheet
    # stops treating it as reconciled with the (now-ignored) statement
    # row.
    assert refreshed_jl.cleared_status == "uncleared"

    # And the journal line is now free to be matched against another
    # statement row, which validates the rollback released the FK.
    line_b = (
        await db_session.execute(
            select(StatementLine).where(
                StatementLine.import_id == imp.id,
                StatementLine.fitid == "FIT-B",
            )
        )
    ).scalar_one()
    matched_b = await match_line(
        db_session, statement_line_id=line_b.id, journal_line_id=jl.id
    )
    assert matched_b.match_status == "matched"
