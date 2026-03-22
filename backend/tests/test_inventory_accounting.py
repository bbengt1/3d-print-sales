from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.inventory_transaction import InventoryTransaction
from app.models.job import Job
from app.models.journal_entry import JournalEntry
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.services.accounting_service import seed_chart_of_accounts
from app.services.inventory_accounting_service import post_cogs_for_sale, post_finished_goods_from_job
from app.services.material_receipt_service import create_material_receipt
from app.schemas.material_receipt import MaterialReceiptCreate


@pytest_asyncio.fixture
async def seed_product(db_session: AsyncSession, seed_material: Material) -> Product:
    product = Product(
        sku="INV-ACCT-001",
        name="Inventory Accounted Product",
        material_id=seed_material.id,
        unit_cost=Decimal("4.00"),
        unit_price=Decimal("12.00"),
        stock_qty=10,
        reorder_point=2,
        is_active=True,
    )
    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)
    return product


@pytest.mark.asyncio
async def test_post_finished_goods_from_job_creates_inventory_journal_and_consumes_receipts(db_session: AsyncSession, seed_material: Material, seed_product: Product):
    await seed_chart_of_accounts(db_session)
    await create_material_receipt(
        db_session,
        material=seed_material,
        payload=MaterialReceiptCreate(
            vendor_name="Vendor A",
            purchase_date=date(2026, 3, 22),
            quantity_purchased_g=Decimal("1000"),
            unit_cost_per_g=Decimal("0.020000"),
            landed_cost_total=Decimal("0.00"),
            valuation_method="lot",
        ),
    )

    job = Job(
        job_number="JOB-ACCT-001",
        date=date(2026, 3, 22),
        material_id=seed_material.id,
        product_id=seed_product.id,
        product_name=seed_product.name,
        qty_per_plate=2,
        num_plates=3,
        material_per_plate_g=Decimal("100"),
        print_time_per_plate_hrs=Decimal("1.0"),
        labor_mins=10,
        design_time_hrs=Decimal("0"),
        shipping_cost=Decimal("0"),
        target_margin_pct=Decimal("25"),
        total_pieces=6,
        material_cost=Decimal("12.00"),
        labor_cost=Decimal("2.00"),
        design_cost=Decimal("0.00"),
        machine_cost=Decimal("3.00"),
        electricity_cost=Decimal("1.00"),
        overhead=Decimal("2.00"),
        total_cost=Decimal("20.00"),
        cost_per_piece=Decimal("3.3333"),
        total_revenue=Decimal("30.00"),
        platform_fees=Decimal("0.00"),
        net_profit=Decimal("10.00"),
        profit_per_piece=Decimal("1.6667"),
        price_per_piece=Decimal("5.00"),
        status="completed",
        inventory_added=True,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    await post_finished_goods_from_job(db_session, job)

    entry = (await db_session.execute(select(JournalEntry).where(JournalEntry.source_type == "job_production", JournalEntry.source_id == str(job.id)))).scalar_one()
    assert entry is not None

    receipt = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.material_id == seed_material.id))).scalar_one()
    assert float(receipt.quantity_remaining_g) == pytest.approx(700.0, rel=1e-5)


@pytest.mark.asyncio
async def test_post_cogs_for_sale_creates_cogs_journal_entry(db_session: AsyncSession, seed_product: Product):
    await seed_chart_of_accounts(db_session)

    sale = Sale(
        sale_number="S-2026-ACCT-001",
        date=date(2026, 3, 22),
        status="paid",
        subtotal=Decimal("25.00"),
        shipping_charged=Decimal("0.00"),
        shipping_cost=Decimal("0.00"),
        platform_fees=Decimal("0.00"),
        tax_collected=Decimal("0.00"),
        total=Decimal("25.00"),
        net_revenue=Decimal("15.00"),
    )
    db_session.add(sale)
    await db_session.flush()
    item = SaleItem(
        sale_id=sale.id,
        product_id=seed_product.id,
        description="Test product",
        quantity=2,
        unit_price=Decimal("12.50"),
        unit_cost=Decimal("4.00"),
        line_total=Decimal("25.00"),
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(sale)

    await post_cogs_for_sale(db_session, sale, [item])

    entry = (await db_session.execute(select(JournalEntry).where(JournalEntry.source_type == "sale_cogs", JournalEntry.source_id == str(sale.id)))).scalar_one()
    assert entry is not None
