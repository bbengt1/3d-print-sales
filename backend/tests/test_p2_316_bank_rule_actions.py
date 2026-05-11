"""#316 P2 deeper: create_receipt / create_payment / create_inter_account_transfer."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.customer import Customer
from app.models.inter_account_transfer import InterAccountTransfer
from app.models.payment import Payment
from app.models.statement_import import StatementLine
from app.models.statement_match_rule import StatementMatchRule
from app.models.vendor import Vendor
from app.services.statement_import_service import import_statement
from app.services.statement_match_rule_service import (
    apply_rules_to_import,
    preview_rules_for_import,
)


SAMPLE_OFX = """
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><DTPOSTED>20260501<TRNAMT>250.00<FITID>F-CUST<NAME>ACME inc payment</STMTTRN>
<STMTTRN><DTPOSTED>20260502<TRNAMT>-180.00<FITID>F-VEND<NAME>Filament Co invoice</STMTTRN>
<STMTTRN><DTPOSTED>20260503<TRNAMT>-1000.00<FITID>F-XFER<NAME>Online transfer to savings</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


async def _bank(db, code="1010", name="Operating") -> Account:
    a = Account(
        code=code, name=name, account_type="asset",
        normal_balance="debit", is_bank_account=True, bank_account_kind="checking",
    )
    db.add(a)
    await db.flush()
    return a


async def _ensure_ar_ap(db):
    if (await db.execute(select(Account).where(Account.code == "1100"))).scalar_one_or_none() is None:
        db.add(Account(code="1100", name="Accounts Receivable", account_type="asset", normal_balance="debit"))
    if (await db.execute(select(Account).where(Account.code == "2000"))).scalar_one_or_none() is None:
        db.add(Account(code="2000", name="Accounts Payable", account_type="liability", normal_balance="credit"))
    await db.flush()


@pytest.mark.asyncio
async def test_create_receipt_posts_je_and_unapplied_payment(db_session):
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session)
    cust = Customer(name="ACME Inc")
    db_session.add(cust)
    await db_session.flush()

    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="ACME receipts", match_type="contains", match_pattern="ACME",
        match_amount_sign="credit", action="create_receipt",
        customer_id=cust.id, priority=10,
    ))
    await db_session.flush()

    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_receipts"] == 1

    payments = (
        await db_session.execute(select(Payment).where(Payment.customer_id == cust.id))
    ).scalars().all()
    assert len(payments) == 1
    assert payments[0].amount == Decimal("250.00")
    assert payments[0].unapplied_amount == Decimal("250.00")

    line = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "F-CUST"))
    ).scalar_one()
    assert line.match_status == "matched"
    assert line.matched_journal_line_id is not None


@pytest.mark.asyncio
async def test_create_payment_posts_ap_je(db_session):
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session)
    vendor = Vendor(name="Filament Co")
    db_session.add(vendor)
    await db_session.flush()

    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Filament Co payments", match_type="contains", match_pattern="Filament Co",
        match_amount_sign="debit", action="create_payment",
        vendor_id=vendor.id, priority=10,
    ))
    await db_session.flush()

    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_payments"] == 1

    line = (
        await db_session.execute(select(StatementLine).where(StatementLine.fitid == "F-VEND"))
    ).scalar_one()
    assert line.match_status == "matched"
    assert line.matched_journal_line_id is not None


@pytest.mark.asyncio
async def test_create_inter_account_transfer_creates_iat(db_session):
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session, code="1010", name="Operating")
    savings = await _bank(db_session, code="1020", name="Savings")

    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Savings transfers", match_type="contains", match_pattern="transfer to savings",
        match_amount_sign="debit", action="create_inter_account_transfer",
        transfer_to_account_id=savings.id, priority=10,
    ))
    await db_session.flush()

    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_inter_account_transfers"] == 1

    iats = (
        await db_session.execute(select(InterAccountTransfer))
    ).scalars().all()
    assert len(iats) == 1
    assert iats[0].from_account_id == bank.id
    assert iats[0].to_account_id == savings.id
    assert iats[0].amount == Decimal("1000.00")


@pytest.mark.asyncio
async def test_create_receipt_skipped_without_customer(db_session):
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="Unconfigured", match_type="contains", match_pattern="ACME",
        match_amount_sign="credit", action="create_receipt",
        customer_id=None, priority=10,
    ))
    await db_session.flush()

    summary = await apply_rules_to_import(db_session, import_id=imp.id)
    assert summary["auto_receipts"] == 0
    assert summary["skipped_unsupported_actions"] >= 1


@pytest.mark.asyncio
async def test_from_line_rejects_oversized_counterparty(client, auth_headers, db_session):
    """Codex P2: counterparty_name is capped at 200 chars in the DB; the
    from-line payload must reject anything longer with a 4xx rather than
    leak a 500 at commit time.
    """
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session)
    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    await db_session.commit()
    line = (
        await db_session.execute(select(StatementLine).where(StatementLine.import_id == imp.id))
    ).scalars().first()

    r = await client.post(
        "/api/v1/banking/rules/from-line",
        headers=auth_headers,
        json={
            "statement_line_id": str(line.id),
            "name": "x",
            "action": "ignore",
            "counterparty_name": "A" * 201,
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_preview_surfaces_target_label(db_session):
    await _ensure_ar_ap(db_session)
    bank = await _bank(db_session, code="1010", name="Operating")
    savings = await _bank(db_session, code="1020", name="Savings")
    imp = await import_statement(
        db_session,
        account_id=bank.id,
        source_format="ofx",
        source_filename="x.ofx",
        content=SAMPLE_OFX.encode(),
    )
    db_session.add(StatementMatchRule(
        name="To savings", match_type="contains", match_pattern="transfer to savings",
        match_amount_sign="debit", action="create_inter_account_transfer",
        transfer_to_account_id=savings.id, priority=10,
    ))
    await db_session.flush()

    preview = await preview_rules_for_import(db_session, import_id=imp.id)
    matched_targets = [
        l["matched_rule"]["target"] for l in preview["lines"] if l["matched_rule"]
    ]
    assert any(t and "Savings" in t for t in matched_targets)
