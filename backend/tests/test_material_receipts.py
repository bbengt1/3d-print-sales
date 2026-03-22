from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.schemas.material_receipt import MaterialReceiptCreate
from app.services.material_receipt_service import create_material_receipt


@pytest.mark.asyncio
async def test_create_material_receipt_calculates_landed_cost_and_remaining_qty(db_session: AsyncSession, seed_material: Material):
    receipt = await create_material_receipt(
        db_session,
        material=seed_material,
        payload=MaterialReceiptCreate(
            vendor_name="MatterHackers",
            purchase_date=date(2026, 3, 22),
            receipt_number="PO-1001",
            quantity_purchased_g=Decimal("1000"),
            unit_cost_per_g=Decimal("0.020000"),
            landed_cost_total=Decimal("5.00"),
            valuation_method="lot",
        ),
    )

    assert receipt.quantity_remaining_g == Decimal("1000")
    assert receipt.landed_cost_per_g == Decimal("0.005")
    assert receipt.total_cost == Decimal("25.00")


@pytest.mark.asyncio
async def test_material_receipt_updates_material_average_cost(db_session: AsyncSession, seed_material: Material):
    await create_material_receipt(
        db_session,
        material=seed_material,
        payload=MaterialReceiptCreate(
            vendor_name="Vendor A",
            purchase_date=date(2026, 3, 22),
            quantity_purchased_g=Decimal("1000"),
            unit_cost_per_g=Decimal("0.020000"),
            landed_cost_total=Decimal("0.00"),
            valuation_method="average",
        ),
    )
    await create_material_receipt(
        db_session,
        material=seed_material,
        payload=MaterialReceiptCreate(
            vendor_name="Vendor B",
            purchase_date=date(2026, 3, 23),
            quantity_purchased_g=Decimal("500"),
            unit_cost_per_g=Decimal("0.030000"),
            landed_cost_total=Decimal("5.00"),
            valuation_method="average",
        ),
    )

    refreshed = (await db_session.execute(select(Material).where(Material.id == seed_material.id))).scalar_one()
    assert float(refreshed.cost_per_g) == pytest.approx(45 / 1500, rel=1e-4)


@pytest.mark.asyncio
async def test_receipts_are_persisted_by_material(db_session: AsyncSession, seed_material: Material):
    await create_material_receipt(
        db_session,
        material=seed_material,
        payload=MaterialReceiptCreate(
            vendor_name="Vendor A",
            purchase_date=date(2026, 3, 22),
            quantity_purchased_g=Decimal("1000"),
            unit_cost_per_g=Decimal("0.020000"),
            landed_cost_total=Decimal("2.00"),
            valuation_method="lot",
        ),
    )

    receipts = (await db_session.execute(select(MaterialReceipt).where(MaterialReceipt.material_id == seed_material.id))).scalars().all()
    assert len(receipts) == 1
    assert receipts[0].vendor_name == "Vendor A"
