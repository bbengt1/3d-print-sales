from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.account import Account
from app.models.account_budget import AccountBudget


router = APIRouter(prefix="/budgets", tags=["Budgets"])


class BudgetUpsertRow(BaseModel):
    account_id: uuid.UUID
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal


class BudgetUpsertRequest(BaseModel):
    rows: list[BudgetUpsertRow] = Field(..., min_length=1)


class BudgetResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    year: int
    month: int
    amount: Decimal


def _to_response(b: AccountBudget) -> BudgetResponse:
    return BudgetResponse(
        id=b.id, account_id=b.account_id, year=b.year, month=b.month, amount=Decimal(b.amount),
    )


@router.get("", response_model=list[BudgetResponse], summary="List budgets")
async def list_budgets(user: CurrentUser, db: DB, year: int | None = None, account_id: uuid.UUID | None = None):
    stmt = select(AccountBudget).order_by(AccountBudget.year, AccountBudget.month)
    if year is not None:
        stmt = stmt.where(AccountBudget.year == year)
    if account_id is not None:
        stmt = stmt.where(AccountBudget.account_id == account_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("/upsert", response_model=list[BudgetResponse], status_code=status.HTTP_200_OK, summary="Upsert per (account, year, month)")
async def upsert_budgets(body: BudgetUpsertRequest, user: CurrentUser, db: DB):
    # Validate all account ids exist + are income/expense (refuses balance-sheet accts)
    account_ids = {r.account_id for r in body.rows}
    accounts = (
        await db.execute(select(Account).where(Account.id.in_(account_ids)))
    ).scalars().all()
    by_id = {a.id: a for a in accounts}
    missing = account_ids - set(by_id.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"Accounts not found: {sorted(str(m) for m in missing)}")
    for a in accounts:
        if a.account_type not in ("revenue", "cogs", "expense"):
            raise HTTPException(
                status_code=400,
                detail=f"Account {a.code} is type {a.account_type}; budgets only apply to income/expense",
            )

    out: list[BudgetResponse] = []
    for r in body.rows:
        existing = (
            await db.execute(
                select(AccountBudget).where(
                    AccountBudget.account_id == r.account_id,
                    AccountBudget.year == r.year,
                    AccountBudget.month == r.month,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.amount = r.amount
            out.append(_to_response(existing))
        else:
            new = AccountBudget(account_id=r.account_id, year=r.year, month=r.month, amount=r.amount)
            db.add(new)
            await db.flush()
            out.append(_to_response(new))
    await db.commit()
    return out


@router.delete("/{budget_id}", status_code=204, summary="Delete a budget row")
async def delete_budget(budget_id: uuid.UUID, user: CurrentUser, db: DB):
    b = (await db.execute(select(AccountBudget).where(AccountBudget.id == budget_id))).scalar_one_or_none()
    if not b:
        raise HTTPException(status_code=404, detail="Budget row not found")
    await db.delete(b)
    await db.commit()


@router.post("/copy-year", response_model=dict, summary="Copy all budgets from one year to another (idempotent — skips existing)")
async def copy_year(user: CurrentUser, db: DB, from_year: int, to_year: int):
    if from_year == to_year:
        raise HTTPException(status_code=400, detail="from_year and to_year must differ")
    src = (
        await db.execute(select(AccountBudget).where(AccountBudget.year == from_year))
    ).scalars().all()
    copied = 0
    skipped = 0
    for r in src:
        existing = (
            await db.execute(
                select(AccountBudget).where(
                    AccountBudget.account_id == r.account_id,
                    AccountBudget.year == to_year,
                    AccountBudget.month == r.month,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        db.add(
            AccountBudget(
                account_id=r.account_id,
                year=to_year,
                month=r.month,
                amount=r.amount,
            )
        )
        copied += 1
    await db.commit()
    return {"copied": copied, "skipped": skipped, "from_year": from_year, "to_year": to_year}
