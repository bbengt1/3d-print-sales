from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.statement_import import StatementLine
from app.models.statement_match_rule import StatementMatchRule
from app.services.statement_import_service import import_statement
from app.services.statement_match_rule_service import (
    StatementMatchRuleError,
    apply_rules_to_import,
    evaluate_rules_for_line,
    validate_rule,
)


SAMPLE_OFX = """
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><DTPOSTED>20260501<TRNAMT>-25.00<FITID>F1<NAME>Filament supplier</STMTTRN>
<STMTTRN><DTPOSTED>20260503<TRNAMT>500.00<FITID>F2<NAME>Etsy payout</STMTTRN>
<STMTTRN><DTPOSTED>20260505<TRNAMT>-3.50<FITID>F3<NAME>ATM CHECK FEE</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


async def _bank(db_session) -> Account:
    a = Account(
        code="1010", name="Operating", account_type="asset",
        normal_balance="debit", is_bank_account=True, bank_account_kind="checking",
    )
    db_session.add(a)
    await db_session.flush()
    return a


def test_validate_rule_unknown_type():
    with pytest.raises(StatementMatchRuleError):
        validate_rule(match_type="bogus", match_pattern="x", match_amount_sign="any", action="ignore")


def test_validate_rule_invalid_regex():
    with pytest.raises(StatementMatchRuleError):
        validate_rule(match_type="regex", match_pattern="[unclosed", match_amount_sign="any", action="ignore")


def test_validate_rule_unsupported_action():
    with pytest.raises(StatementMatchRuleError):
        validate_rule(match_type="contains", match_pattern="x", match_amount_sign="any", action="create_receipt")


@pytest.mark.asyncio
async def test_evaluate_contains_match(db_session):
    a = await _bank(db_session)
    rule = StatementMatchRule(
        name="ATM fees", match_type="contains", match_pattern="ATM",
        match_amount_sign="debit", action="ignore", priority=10,
    )
    db_session.add(rule)
    line = StatementLine(
        import_id=__import__("uuid").uuid4(),  # placeholder; not persisted
        account_id=a.id,
        posted_date=datetime.date(2026, 5, 5),
        amount=Decimal("-3.50"),
        description="ATM CHECK FEE",
        match_status="unmatched",
    )
    matched = await evaluate_rules_for_line(db_session, line)
    assert matched is not None
    assert matched.id == rule.id


@pytest.mark.asyncio
async def test_evaluate_regex_match(db_session):
    a = await _bank(db_session)
    rule = StatementMatchRule(
        name="Etsy payouts", match_type="regex", match_pattern=r"^Etsy\s+payout",
        match_amount_sign="credit", action="ignore", priority=10,
    )
    db_session.add(rule)
    line = StatementLine(
        import_id=__import__("uuid").uuid4(),
        account_id=a.id,
        posted_date=datetime.date(2026, 5, 3),
        amount=Decimal("500.00"),
        description="Etsy payout 0501",
        match_status="unmatched",
    )
    assert (await evaluate_rules_for_line(db_session, line)) is not None


@pytest.mark.asyncio
async def test_evaluate_sign_filter_blocks(db_session):
    a = await _bank(db_session)
    rule = StatementMatchRule(
        name="Debits only", match_type="contains", match_pattern="payout",
        match_amount_sign="debit", action="ignore", priority=10,
    )
    db_session.add(rule)
    line = StatementLine(
        import_id=__import__("uuid").uuid4(),
        account_id=a.id,
        posted_date=datetime.date(2026, 5, 3),
        amount=Decimal("500.00"),  # credit, not debit
        description="Etsy payout",
        match_status="unmatched",
    )
    assert (await evaluate_rules_for_line(db_session, line)) is None


@pytest.mark.asyncio
async def test_priority_ordering(db_session):
    a = await _bank(db_session)
    db_session.add(StatementMatchRule(
        name="Low priority", match_type="contains", match_pattern="payout",
        match_amount_sign="any", action="ignore", priority=200,
    ))
    db_session.add(StatementMatchRule(
        name="High priority", match_type="contains", match_pattern="payout",
        match_amount_sign="any", action="ignore", priority=10,
    ))
    await db_session.flush()
    line = StatementLine(
        import_id=__import__("uuid").uuid4(),
        account_id=a.id,
        posted_date=datetime.date(2026, 5, 3),
        amount=Decimal("500.00"),
        description="Etsy payout",
        match_status="unmatched",
    )
    matched = await evaluate_rules_for_line(db_session, line)
    assert matched is not None
    assert matched.name == "High priority"


@pytest.mark.asyncio
async def test_inactive_rule_ignored(db_session):
    a = await _bank(db_session)
    db_session.add(StatementMatchRule(
        name="Inactive", match_type="contains", match_pattern="payout",
        match_amount_sign="any", action="ignore", is_active=False, priority=10,
    ))
    await db_session.flush()
    line = StatementLine(
        import_id=__import__("uuid").uuid4(),
        account_id=a.id,
        posted_date=datetime.date(2026, 5, 3),
        amount=Decimal("500.00"),
        description="Etsy payout",
        match_status="unmatched",
    )
    assert (await evaluate_rules_for_line(db_session, line)) is None


@pytest.mark.asyncio
async def test_rules_applied_during_import(db_session):
    a = await _bank(db_session)
    db_session.add(StatementMatchRule(
        name="Auto-ignore ATM fees", match_type="contains", match_pattern="ATM",
        match_amount_sign="any", action="ignore", priority=10,
    ))
    await db_session.flush()

    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    await db_session.commit()
    rows = (await db_session.execute(select(StatementLine).where(StatementLine.import_id == imp.id))).scalars().all()
    statuses = {r.fitid: r.match_status for r in rows}
    # The ATM fee should be auto-ignored
    assert statuses["F3"] == "ignored"
    # Others remain unmatched
    assert statuses["F1"] == "unmatched"
    assert statuses["F2"] == "unmatched"


@pytest.mark.asyncio
async def test_apply_rules_to_import_summary(db_session):
    a = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=a.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Block all credits", match_type="contains", match_pattern="",
        match_amount_sign="credit", action="ignore", priority=10,
    ))
    await db_session.flush()
    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_ignored"] >= 1
