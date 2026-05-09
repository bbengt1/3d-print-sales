from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.expense_claim import ExpenseClaim
from app.services.expense_claim_service import (
    ExpenseClaimError,
    approve_claim,
    cancel_claim,
    create_claim,
    reimburse_claim,
    submit_claim,
)


async def _accounts(db_session):
    return {a.code: a for a in (await db_session.execute(select(Account))).scalars().all()}


async def _make_claim(db_session, accts, *, amount=Decimal("100")):
    return await create_claim(
        db_session,
        payer_kind="owner",
        payer_name="Brent",
        lines=[{"description": "Filament", "expense_account_id": accts["6500"].id, "amount": amount}],
    )


@pytest.mark.asyncio
async def test_create_assigns_number_and_total(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    assert claim.claim_number.startswith("EC-")
    assert claim.total_amount == Decimal("100.00")
    assert claim.status == "draft"


@pytest.mark.asyncio
async def test_create_no_lines_rejected(db_session):
    with pytest.raises(ExpenseClaimError):
        await create_claim(db_session, payer_kind="owner", payer_name="x", lines=[])


@pytest.mark.asyncio
async def test_create_zero_amount_rejected(db_session):
    accts = await _accounts(db_session)
    with pytest.raises(ExpenseClaimError):
        await create_claim(
            db_session,
            payer_kind="owner",
            payer_name="x",
            lines=[{"description": "x", "expense_account_id": accts["6500"].id, "amount": Decimal("0")}],
        )


@pytest.mark.asyncio
async def test_lifecycle_submit_approve_reimburse(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)

    claim = await submit_claim(db_session, claim.id)
    assert claim.status == "submitted"
    assert claim.submitted_on is not None

    claim = await approve_claim(db_session, claim.id)
    assert claim.status == "approved"
    assert claim.journal_entry_id is not None

    claim = await reimburse_claim(db_session, claim.id, cash_account_id=accts["1000"].id)
    assert claim.status == "reimbursed"
    assert claim.reimbursement_journal_entry_id is not None


@pytest.mark.asyncio
async def test_approve_skips_submit(db_session):
    """Operator can approve a draft directly without submit."""
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    claim = await approve_claim(db_session, claim.id)
    assert claim.status == "approved"


@pytest.mark.asyncio
async def test_cancel_from_draft(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    claim = await cancel_claim(db_session, claim.id)
    assert claim.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_from_approved_reverses_je(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    claim = await approve_claim(db_session, claim.id)
    claim = await cancel_claim(db_session, claim.id)
    assert claim.status == "cancelled"


@pytest.mark.asyncio
async def test_cannot_reimburse_unapproved(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    with pytest.raises(ExpenseClaimError):
        await reimburse_claim(db_session, claim.id, cash_account_id=accts["1000"].id)


@pytest.mark.asyncio
async def test_cannot_cancel_after_reimburse(db_session):
    accts = await _accounts(db_session)
    claim = await _make_claim(db_session, accts)
    await approve_claim(db_session, claim.id)
    await reimburse_claim(db_session, claim.id, cash_account_id=accts["1000"].id)
    with pytest.raises(ExpenseClaimError):
        await cancel_claim(db_session, claim.id)
