from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentAdmin
from app.models.account import Account
from app.models.accounting_period import AccountingPeriod
from app.models.bill import Bill
from app.models.bill_payment import BillPayment
from app.models.expense_category import ExpenseCategory
from app.models.journal_entry import JournalEntry
from app.models.recurring_expense import RecurringExpense
from app.models.vendor import Vendor
from app.schemas.accounting import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AccountingPeriodCreate,
    AccountingPeriodResponse,
    AccountingPeriodStatusUpdate,
    AccountingPeriodUpdate,
    JournalEntryCreate,
    JournalEntryResponse,
    JournalEntryReverse,
)
from app.schemas.bills import (
    BillCreate,
    BillPaymentCreate,
    BillPaymentResponse,
    BillResponse,
    BillUpdate,
)
from app.schemas.expenses import (
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
    ExpenseCategoryUpdate,
    VendorCreate,
    VendorResponse,
    VendorUpdate,
)
from app.schemas.recurring_expenses import (
    ExpenseSummaryRow,
    RecurringExpenseCreate,
    RecurringExpenseGenerate,
    RecurringExpenseResponse,
    RecurringExpenseUpdate,
)
from app.services.accounting_service import AccountingValidationError, create_journal_entry, reverse_journal_entry, set_accounting_period_status
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/accounting", tags=["Accounting"])


def _validate_period_dates(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")


def _validate_expense_account(account: Account | None) -> None:
    if not account:
        raise HTTPException(status_code=404, detail="Mapped account not found")
    if account.account_type not in {"expense", "cogs"}:
        raise HTTPException(status_code=400, detail="Expense categories must map to an expense or cogs account")


def _compute_bill_status(amount: float, amount_paid: float, existing_status: str | None = None) -> str:
    if existing_status == "void":
        return "void"
    if amount_paid <= 0:
        return "open"
    if amount_paid >= amount:
        return "paid"
    return "partially_paid"


def _next_due_date(current, frequency: str):
    from datetime import timedelta

    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "monthly":
        return current + timedelta(days=30)
    if frequency == "quarterly":
        return current + timedelta(days=90)
    if frequency == "yearly":
        return current + timedelta(days=365)
    return current


@router.post(
    "/vendors",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor (admin only)",
)
async def create_vendor(body: VendorCreate, admin: CurrentAdmin, db: DB):
    existing = await db.execute(select(Vendor).where(Vendor.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Vendor name already exists")
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return vendor


@router.get(
    "/vendors",
    response_model=list[VendorResponse],
    summary="List vendors (admin only)",
)
async def list_vendors(admin: CurrentAdmin, db: DB, is_active: bool | None = Query(None)):
    stmt = select(Vendor).order_by(Vendor.name.asc())
    if is_active is not None:
        stmt = stmt.where(Vendor.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put(
    "/vendors/{vendor_id}",
    response_model=VendorResponse,
    summary="Update vendor (admin only)",
)
async def update_vendor(vendor_id: uuid.UUID, body: VendorUpdate, admin: CurrentAdmin, db: DB):
    vendor = (await db.execute(select(Vendor).where(Vendor.id == vendor_id))).scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    await db.commit()
    await db.refresh(vendor)
    return vendor


@router.post(
    "/bills",
    response_model=BillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create bill/expense (admin only)",
)
async def create_bill(body: BillCreate, admin: CurrentAdmin, db: DB):
    account = (await db.execute(select(Account).where(Account.id == body.account_id))).scalar_one_or_none()
    _validate_expense_account(account)
    if body.vendor_id:
        vendor = (await db.execute(select(Vendor).where(Vendor.id == body.vendor_id))).scalar_one_or_none()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
    if body.expense_category_id:
        category = (await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == body.expense_category_id))).scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Expense category not found")

    bill = Bill(**body.model_dump(), status="open")
    db.add(bill)
    await db.commit()
    result = await db.execute(select(Bill).options(selectinload(Bill.payments)).where(Bill.id == bill.id))
    return result.scalar_one()


@router.get(
    "/bills",
    response_model=list[BillResponse],
    summary="List bills/expenses (admin only)",
)
async def list_bills(admin: CurrentAdmin, db: DB, status_filter: str | None = Query(None, alias="status")):
    stmt = select(Bill).options(selectinload(Bill.payments)).order_by(Bill.issue_date.desc(), Bill.created_at.desc())
    if status_filter:
        stmt = stmt.where(Bill.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put(
    "/bills/{bill_id}",
    response_model=BillResponse,
    summary="Update bill/expense (admin only)",
)
async def update_bill(bill_id: uuid.UUID, body: BillUpdate, admin: CurrentAdmin, db: DB):
    bill = (await db.execute(select(Bill).options(selectinload(Bill.payments)).where(Bill.id == bill_id))).scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    try:
        await assert_financial_date_editable(db, target_date=bill.issue_date, detail_prefix="This bill")
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updates = body.model_dump(exclude_unset=True)
    if "account_id" in updates:
        account = (await db.execute(select(Account).where(Account.id == updates["account_id"]))).scalar_one_or_none()
        _validate_expense_account(account)
    if "vendor_id" in updates and updates["vendor_id"]:
        vendor = (await db.execute(select(Vendor).where(Vendor.id == updates["vendor_id"]))).scalar_one_or_none()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")
    if "expense_category_id" in updates and updates["expense_category_id"]:
        category = (await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == updates["expense_category_id"]))).scalar_one_or_none()
        if not category:
            raise HTTPException(status_code=404, detail="Expense category not found")

    for field, value in updates.items():
        setattr(bill, field, value)

    if bill.status != "void":
        bill.status = _compute_bill_status(float(bill.amount), float(bill.amount_paid), bill.status)

    await db.commit()
    result = await db.execute(select(Bill).options(selectinload(Bill.payments)).where(Bill.id == bill.id))
    return result.scalar_one()


@router.post(
    "/bills/{bill_id}/payments",
    response_model=BillPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record bill payment (admin only)",
)
async def create_bill_payment(bill_id: uuid.UUID, body: BillPaymentCreate, admin: CurrentAdmin, db: DB):
    bill = (await db.execute(select(Bill).options(selectinload(Bill.payments)).where(Bill.id == bill_id))).scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.status == "void":
        raise HTTPException(status_code=400, detail="Cannot pay a void bill")
    if float(bill.amount_paid + body.amount) > float(bill.amount):
        raise HTTPException(status_code=400, detail="Payment exceeds remaining balance")

    payment = BillPayment(bill_id=bill.id, **body.model_dump())
    db.add(payment)
    bill.amount_paid = bill.amount_paid + body.amount
    bill.status = _compute_bill_status(float(bill.amount), float(bill.amount_paid), bill.status)
    if body.payment_method:
        bill.payment_method = body.payment_method
    await db.commit()
    await db.refresh(payment)
    return payment


@router.post(
    "/recurring-expenses",
    response_model=RecurringExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create recurring expense template (admin only)",
)
async def create_recurring_expense(body: RecurringExpenseCreate, admin: CurrentAdmin, db: DB):
    account = (await db.execute(select(Account).where(Account.id == body.account_id))).scalar_one_or_none()
    _validate_expense_account(account)
    recurring = RecurringExpense(**body.model_dump())
    db.add(recurring)
    await db.commit()
    await db.refresh(recurring)
    return recurring


@router.get(
    "/recurring-expenses",
    response_model=list[RecurringExpenseResponse],
    summary="List recurring expense templates (admin only)",
)
async def list_recurring_expenses(admin: CurrentAdmin, db: DB, is_active: bool | None = Query(None)):
    stmt = select(RecurringExpense).order_by(RecurringExpense.next_due_date.asc(), RecurringExpense.created_at.asc())
    if is_active is not None:
        stmt = stmt.where(RecurringExpense.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put(
    "/recurring-expenses/{recurring_id}",
    response_model=RecurringExpenseResponse,
    summary="Update recurring expense template (admin only)",
)
async def update_recurring_expense(recurring_id: uuid.UUID, body: RecurringExpenseUpdate, admin: CurrentAdmin, db: DB):
    recurring = (await db.execute(select(RecurringExpense).where(RecurringExpense.id == recurring_id))).scalar_one_or_none()
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    updates = body.model_dump(exclude_unset=True)
    if "account_id" in updates:
        account = (await db.execute(select(Account).where(Account.id == updates["account_id"]))).scalar_one_or_none()
        _validate_expense_account(account)
    for field, value in updates.items():
        setattr(recurring, field, value)
    await db.commit()
    await db.refresh(recurring)
    return recurring


@router.post(
    "/recurring-expenses/{recurring_id}/generate",
    response_model=BillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate bill from recurring expense template (admin only)",
)
async def generate_recurring_bill(recurring_id: uuid.UUID, body: RecurringExpenseGenerate, admin: CurrentAdmin, db: DB):
    recurring = (await db.execute(select(RecurringExpense).where(RecurringExpense.id == recurring_id))).scalar_one_or_none()
    if not recurring:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    if not recurring.is_active:
        raise HTTPException(status_code=400, detail="Recurring expense is inactive")
    if body.as_of_date < recurring.next_due_date:
        raise HTTPException(status_code=400, detail="Recurring expense is not due yet")

    bill = Bill(
        vendor_id=recurring.vendor_id,
        expense_category_id=recurring.expense_category_id,
        account_id=recurring.account_id,
        description=recurring.description,
        issue_date=body.as_of_date,
        due_date=body.as_of_date,
        amount=recurring.amount,
        tax_amount=recurring.tax_amount,
        payment_method=recurring.payment_method,
        notes=recurring.notes,
        status="open",
    )
    db.add(bill)
    recurring.last_generated_at = recurring.updated_at
    recurring.next_due_date = _next_due_date(recurring.next_due_date, recurring.frequency)
    await db.commit()
    result = await db.execute(select(Bill).options(selectinload(Bill.payments)).where(Bill.id == bill.id))
    return result.scalar_one()


@router.get(
    "/reports/expenses/by-category",
    response_model=list[ExpenseSummaryRow],
    summary="Expense summary by category (admin only)",
)
async def expense_summary_by_category(admin: CurrentAdmin, db: DB):
    rows = (await db.execute(select(ExpenseCategory, Bill).join(Bill, Bill.expense_category_id == ExpenseCategory.id))).all()
    summary = {}
    for category, bill in rows:
        key = str(category.id)
        row = summary.setdefault(key, {"key": key, "label": category.name, "total_amount": 0, "bill_count": 0})
        row["total_amount"] += bill.amount
        row["bill_count"] += 1
    return list(summary.values())


@router.get(
    "/reports/expenses/by-vendor",
    response_model=list[ExpenseSummaryRow],
    summary="Expense summary by vendor (admin only)",
)
async def expense_summary_by_vendor(admin: CurrentAdmin, db: DB):
    rows = (await db.execute(select(Vendor, Bill).join(Bill, Bill.vendor_id == Vendor.id))).all()
    summary = {}
    for vendor, bill in rows:
        key = str(vendor.id)
        row = summary.setdefault(key, {"key": key, "label": vendor.name, "total_amount": 0, "bill_count": 0})
        row["total_amount"] += bill.amount
        row["bill_count"] += 1
    return list(summary.values())


@router.post(
    "/expense-categories",
    response_model=ExpenseCategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create expense category (admin only)",
)
async def create_expense_category(body: ExpenseCategoryCreate, admin: CurrentAdmin, db: DB):
    existing = await db.execute(select(ExpenseCategory).where(ExpenseCategory.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Expense category name already exists")
    account = (await db.execute(select(Account).where(Account.id == body.account_id))).scalar_one_or_none()
    _validate_expense_account(account)
    category = ExpenseCategory(**body.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.get(
    "/expense-categories",
    response_model=list[ExpenseCategoryResponse],
    summary="List expense categories (admin only)",
)
async def list_expense_categories(admin: CurrentAdmin, db: DB, is_active: bool | None = Query(None)):
    stmt = select(ExpenseCategory).order_by(ExpenseCategory.name.asc())
    if is_active is not None:
        stmt = stmt.where(ExpenseCategory.is_active == is_active)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put(
    "/expense-categories/{category_id}",
    response_model=ExpenseCategoryResponse,
    summary="Update expense category (admin only)",
)
async def update_expense_category(category_id: uuid.UUID, body: ExpenseCategoryUpdate, admin: CurrentAdmin, db: DB):
    category = (await db.execute(select(ExpenseCategory).where(ExpenseCategory.id == category_id))).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Expense category not found")
    updates = body.model_dump(exclude_unset=True)
    if "account_id" in updates:
        account = (await db.execute(select(Account).where(Account.id == updates["account_id"]))).scalar_one_or_none()
        _validate_expense_account(account)
    for field, value in updates.items():
        setattr(category, field, value)
    await db.commit()
    await db.refresh(category)
    return category


    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create account (admin only)",
)
async def create_account(body: AccountCreate, admin: CurrentAdmin, db: DB):
    existing = await db.execute(select(Account).where(Account.code == body.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account code already exists")

    if body.parent_id:
        parent = (await db.execute(select(Account).where(Account.id == body.parent_id))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")

    account = Account(**body.model_dump(), is_system=False)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.put(
    "/accounts/{account_id}",
    response_model=AccountResponse,
    summary="Update account (admin only)",
)
async def update_account(account_id: uuid.UUID, body: AccountUpdate, admin: CurrentAdmin, db: DB):
    account = (await db.execute(select(Account).where(Account.id == account_id))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    updates = body.model_dump(exclude_unset=True)
    if "parent_id" in updates and updates["parent_id"]:
        parent = (await db.execute(select(Account).where(Account.id == updates["parent_id"]))).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        if parent.id == account.id:
            raise HTTPException(status_code=400, detail="Account cannot be its own parent")

    for field, value in updates.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account


@router.get(
    "/accounts",
    response_model=list[AccountResponse],
    summary="List chart of accounts (admin only)",
)
async def list_accounts(
    admin: CurrentAdmin,
    db: DB,
    is_active: bool | None = Query(None),
    account_type: str | None = Query(None),
):
    stmt = select(Account).order_by(Account.code.asc())
    if is_active is not None:
        stmt = stmt.where(Account.is_active == is_active)
    if account_type:
        stmt = stmt.where(Account.account_type == account_type)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "/periods",
    response_model=AccountingPeriodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create accounting period (admin only)",
)
async def create_period(body: AccountingPeriodCreate, admin: CurrentAdmin, db: DB):
    _validate_period_dates(body.start_date, body.end_date)
    existing = await db.execute(select(AccountingPeriod).where(AccountingPeriod.period_key == body.period_key))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Accounting period key already exists")

    period = AccountingPeriod(**body.model_dump())
    db.add(period)
    await db.commit()
    await db.refresh(period)
    return period


@router.get(
    "/periods",
    response_model=list[AccountingPeriodResponse],
    summary="List accounting periods (admin only)",
)
async def list_periods(admin: CurrentAdmin, db: DB, status_filter: str | None = Query(None, alias="status")):
    stmt = select(AccountingPeriod).order_by(AccountingPeriod.start_date.desc())
    if status_filter:
        stmt = stmt.where(AccountingPeriod.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.put(
    "/periods/{period_id}",
    response_model=AccountingPeriodResponse,
    summary="Update accounting period (admin only)",
)
async def update_period(period_id: uuid.UUID, body: AccountingPeriodUpdate, admin: CurrentAdmin, db: DB):
    period = (await db.execute(select(AccountingPeriod).where(AccountingPeriod.id == period_id))).scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Accounting period not found")
    if period.status == "locked":
        raise HTTPException(status_code=400, detail="Locked accounting periods cannot be edited")

    updates = body.model_dump(exclude_unset=True)
    start_date = updates.get("start_date", period.start_date)
    end_date = updates.get("end_date", period.end_date)
    _validate_period_dates(start_date, end_date)

    for field, value in updates.items():
        setattr(period, field, value)

    await db.commit()
    await db.refresh(period)
    return period


@router.post(
    "/periods/{period_id}/status",
    response_model=AccountingPeriodResponse,
    summary="Change accounting period status (admin only)",
)
async def change_period_status(period_id: uuid.UUID, body: AccountingPeriodStatusUpdate, admin: CurrentAdmin, db: DB):
    try:
        period = await set_accounting_period_status(db, period_id=period_id, status=body.status)
    except AccountingValidationError as exc:
        detail = str(exc)
        code = 404 if detail == "Accounting period not found." else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return period


@router.post(
    "/journal-entries",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and post a journal entry (admin only)",
)
async def create_entry(body: JournalEntryCreate, admin: CurrentAdmin, db: DB):
    try:
        entry = await create_journal_entry(db, body)
    except AccountingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry.id)
    )
    return result.scalar_one()


@router.post(
    "/journal-entries/{entry_id}/reverse",
    response_model=JournalEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a posted journal entry (admin only)",
)
async def reverse_entry(entry_id: uuid.UUID, body: JournalEntryReverse, admin: CurrentAdmin, db: DB):
    try:
        entry = await reverse_journal_entry(db, entry_id=entry_id, payload=body)
    except AccountingValidationError as exc:
        detail = str(exc)
        code = 404 if detail == "Journal entry not found." else 400
        raise HTTPException(status_code=code, detail=detail) from exc

    result = await db.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry.id)
    )
    return result.scalar_one()


@router.get(
    "/journal-entries",
    response_model=list[JournalEntryResponse],
    summary="List journal entries (admin only)",
)
async def list_entries(
    admin: CurrentAdmin,
    db: DB,
    status_filter: str | None = Query(None, alias="status"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    stmt = select(JournalEntry).options(selectinload(JournalEntry.lines)).order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    if status_filter:
        stmt = stmt.where(JournalEntry.status == status_filter)
    if date_from:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get(
    "/journal-entries/{entry_id}",
    response_model=JournalEntryResponse,
    summary="Get journal entry by ID (admin only)",
)
async def get_entry(entry_id: uuid.UUID, admin: CurrentAdmin, db: DB):
    result = await db.execute(
        select(JournalEntry).options(selectinload(JournalEntry.lines)).where(JournalEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry
