"""#324 P2 deeper: approval-workflow integration + reimburse-as-bill."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.account import Account
from app.models.approval_request import ApprovalRequest
from app.models.bill import Bill
from app.models.expense_claim import ExpenseClaim
from app.models.setting import Setting
from app.models.vendor import Vendor
from app.services.expense_claim_service import (
    approve_claim,
    create_claim,
    reimburse_claim_as_bill,
    submit_claim_for_approval,
)


async def _seed_accounts(db_session):
    """Ensure the COA codes the service expects are present (the chart
    seeder is run by the db_session fixture, but explicit additions guard
    against fixture drift)."""
    for code, name, kind, normal in (
        ("2000", "Accounts Payable", "liability", "credit"),
        ("2300", "Owner Reimbursable Liability", "liability", "credit"),
    ):
        if (
            await db_session.execute(select(Account).where(Account.code == code))
        ).scalar_one_or_none() is None:
            db_session.add(
                Account(code=code, name=name, account_type=kind, normal_balance=normal)
            )
    expense = (await db_session.execute(select(Account).where(Account.code == "6800"))).scalar_one_or_none()
    if expense is None:
        expense = Account(code="6800", name="Mileage", account_type="expense", normal_balance="debit")
        db_session.add(expense)
    await db_session.flush()
    return expense


async def _make_claim(db_session, expense):
    return await create_claim(
        db_session,
        payer_kind="owner",
        payer_name="Brent",
        lines=[{
            "description": "Filament",
            "expense_account_id": expense.id,
            "amount": Decimal("50"),
        }],
    )


@pytest.mark.asyncio
async def test_submit_creates_approval_request_when_setting_on(client: AsyncClient, auth_headers, db_session):
    expense = await _seed_accounts(db_session)
    db_session.add(Setting(key="expense_claims.require_approval_to_approve", value="true"))
    await db_session.flush()
    claim = await _make_claim(db_session, expense)
    await db_session.commit()

    r = await client.post(f"/api/v1/expense-claims/{claim.id}/submit", headers=auth_headers)
    assert r.status_code == 200

    requests = (
        await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.entity_id == str(claim.id))
        )
    ).scalars().all()
    assert len(requests) == 1
    assert requests[0].action_type == "expense_claim_approval"
    assert requests[0].status == "pending"

    # Direct /approve must refuse when the setting is on.
    r2 = await client.post(
        f"/api/v1/expense-claims/{claim.id}/approve", json={}, headers=auth_headers
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_approval_request_approve_runs_approve_claim(client: AsyncClient, auth_headers, db_session):
    expense = await _seed_accounts(db_session)
    db_session.add(Setting(key="expense_claims.require_approval_to_approve", value="true"))
    await db_session.flush()
    claim = await _make_claim(db_session, expense)
    # Need a user_id; the auth_headers fixture seeds an admin — pull it.
    from app.models.user import User
    admin = (await db_session.execute(select(User).where(User.role == "admin"))).scalar_one()
    await submit_claim_for_approval(db_session, claim.id, requested_by_user_id=admin.id)
    await db_session.commit()

    ar = (
        await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.entity_id == str(claim.id))
        )
    ).scalar_one()

    r = await client.post(
        f"/api/v1/approvals/{ar.id}/approve",
        json={"decision_notes": "ok"},
        headers=auth_headers,
    )
    assert r.status_code == 200

    # The /approvals endpoint committed in its own session, so our test
    # session has a stale identity-mapped copy. Read post-commit state
    # through a brand-new session.
    from sqlalchemy.ext.asyncio import AsyncSession
    from tests.conftest import TestSession  # type: ignore

    async with TestSession() as s:
        refreshed = (
            await s.execute(select(ExpenseClaim).where(ExpenseClaim.id == claim.id))
        ).scalar_one()
        assert refreshed.status == "approved"
        assert refreshed.journal_entry_id is not None


@pytest.mark.asyncio
async def test_reimburse_as_bill_posts_je_and_creates_bill(db_session):
    expense = await _seed_accounts(db_session)
    claim = await _make_claim(db_session, expense)
    await approve_claim(db_session, claim.id)
    vendor = Vendor(name="Brent (vendor)")
    db_session.add(vendor)
    await db_session.flush()

    out = await reimburse_claim_as_bill(
        db_session, claim.id, vendor_id=vendor.id,
    )
    assert out.status == "reimbursed"
    assert out.bill_id is not None
    assert out.reimbursement_journal_entry_id is not None

    bill = (
        await db_session.execute(select(Bill).where(Bill.id == out.bill_id))
    ).scalar_one()
    assert bill.vendor_id == vendor.id
    assert Decimal(bill.amount) == Decimal("50.00")
    # Account is the owner-reimbursable liability so a later bill payment
    # lands the cash credit against the same balance the conversion JE
    # debited.
    liability = (
        await db_session.execute(select(Account).where(Account.code == "2300"))
    ).scalar_one()
    assert bill.account_id == liability.id


@pytest.mark.asyncio
async def test_reimburse_as_bill_refuses_unknown_vendor(db_session):
    import uuid
    expense = await _seed_accounts(db_session)
    claim = await _make_claim(db_session, expense)
    await approve_claim(db_session, claim.id)

    with pytest.raises(Exception):
        await reimburse_claim_as_bill(
            db_session, claim.id, vendor_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_reimburse_as_bill_blocks_double_link(db_session):
    expense = await _seed_accounts(db_session)
    claim = await _make_claim(db_session, expense)
    await approve_claim(db_session, claim.id)
    vendor = Vendor(name="V")
    db_session.add(vendor)
    await db_session.flush()
    await reimburse_claim_as_bill(db_session, claim.id, vendor_id=vendor.id)

    with pytest.raises(Exception):
        await reimburse_claim_as_bill(db_session, claim.id, vendor_id=vendor.id)
