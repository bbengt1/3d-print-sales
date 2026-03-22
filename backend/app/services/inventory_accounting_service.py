from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.job import Job
from app.models.journal_entry import JournalEntry
from app.models.material_receipt import MaterialReceipt
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.schemas.accounting import JournalEntryCreate, JournalLineCreate
from app.services.accounting_service import create_journal_entry


async def _get_account_by_code(db: AsyncSession, code: str) -> Account:
    result = await db.execute(select(Account).where(Account.code == code))
    account = result.scalar_one_or_none()
    if not account:
        raise ValueError(f"Required account with code {code} not found")
    return account


async def _journal_entry_exists(db: AsyncSession, source_type: str, source_id: str) -> bool:
    result = await db.execute(
        select(JournalEntry.id).where(
            JournalEntry.source_type == source_type,
            JournalEntry.source_id == source_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def consume_material_receipts_for_job(db: AsyncSession, job: Job) -> None:
    if not job.material_id:
        return

    total_material_g = Decimal(job.material_per_plate_g) * job.num_plates
    if total_material_g <= 0:
        return

    receipts = (
        await db.execute(
            select(MaterialReceipt)
            .where(
                MaterialReceipt.material_id == job.material_id,
                MaterialReceipt.quantity_remaining_g > 0,
            )
            .order_by(MaterialReceipt.purchase_date.asc(), MaterialReceipt.created_at.asc())
        )
    ).scalars().all()

    remaining = total_material_g
    for receipt in receipts:
        if remaining <= 0:
            break
        available = Decimal(receipt.quantity_remaining_g)
        consume = min(available, remaining)
        receipt.quantity_remaining_g = available - consume
        remaining -= consume


async def post_finished_goods_from_job(db: AsyncSession, job: Job) -> None:
    source_id = str(job.id)
    if await _journal_entry_exists(db, "job_production", source_id):
        return

    finished_goods = await _get_account_by_code(db, "1400")
    wip = await _get_account_by_code(db, "1300")
    total_value = Decimal(job.cost_per_piece) * job.total_pieces
    if total_value <= 0:
        return

    await create_journal_entry(
        db,
        JournalEntryCreate(
            entry_date=job.date,
            source_type="job_production",
            source_id=source_id,
            memo=f"Production completion for job {job.job_number}",
            lines=[
                JournalLineCreate(account_id=finished_goods.id, entry_type="debit", amount=total_value),
                JournalLineCreate(account_id=wip.id, entry_type="credit", amount=total_value),
            ],
        ),
    )
    await consume_material_receipts_for_job(db, job)


async def post_cogs_for_sale(db: AsyncSession, sale: Sale, items: list[SaleItem]) -> None:
    source_id = str(sale.id)
    if await _journal_entry_exists(db, "sale_cogs", source_id):
        return

    finished_goods = await _get_account_by_code(db, "1400")
    material_cogs = await _get_account_by_code(db, "5000")
    total_cogs = sum(Decimal(item.unit_cost or 0) * item.quantity for item in items if item.product_id)
    if total_cogs <= 0:
        return

    await create_journal_entry(
        db,
        JournalEntryCreate(
            entry_date=sale.date,
            source_type="sale_cogs",
            source_id=source_id,
            memo=f"COGS recognition for sale {sale.sale_number}",
            lines=[
                JournalLineCreate(account_id=material_cogs.id, entry_type="debit", amount=total_cogs),
                JournalLineCreate(account_id=finished_goods.id, entry_type="credit", amount=total_cogs),
            ],
        ),
    )
