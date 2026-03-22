from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.material import Material
from app.services.inventory_service import record_scrap_inventory


@pytest_asyncio.fixture
async def scrap_material(db_session: AsyncSession) -> Material:
    material = Material(
        name="PLA Gray",
        cost_per_g=Decimal("0.025"),
        spool_weight_g=1000,
        spool_price=Decimal("25.00"),
        net_usable_g=1000,
        spools_in_stock=1,
        reorder_point=1,
        active=True,
    )
    db_session.add(material)
    await db_session.commit()
    await db_session.refresh(material)
    return material


@pytest_asyncio.fixture
async def scrap_product(db_session: AsyncSession, scrap_material: Material) -> Product:
    product = Product(
        sku="SCRAP-001",
        name="Scrap Test Product",
        material_id=scrap_material.id,
        unit_cost=Decimal("4.50"),
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
async def test_record_scrap_inventory_reduces_stock_and_creates_txn(db_session: AsyncSession, scrap_product: Product):
    txn = await record_scrap_inventory(
        db_session,
        product=scrap_product,
        quantity=3,
        event_type="scrap",
        reason="Warped prints from bad bed adhesion",
    )

    assert txn.type == "scrap"
    assert txn.quantity == -3
    assert float(txn.unit_cost) == pytest.approx(4.5)
    assert "Warped prints" in (txn.notes or "")
    assert scrap_product.stock_qty == 7


@pytest.mark.asyncio
async def test_record_failed_print_uses_override_cost(db_session: AsyncSession, scrap_product: Product):
    txn = await record_scrap_inventory(
        db_session,
        product=scrap_product,
        quantity=2,
        event_type="failed_print",
        reason="Nozzle clog",
        notes="Batch 2 overnight run",
        unit_cost=Decimal("5.25"),
    )

    assert txn.type == "failed_print"
    assert float(txn.unit_cost) == pytest.approx(5.25)
    assert "Nozzle clog" in (txn.notes or "")
    assert "Batch 2 overnight run" in (txn.notes or "")
    assert scrap_product.stock_qty == 8


@pytest.mark.asyncio
async def test_record_scrap_rejects_invalid_quantity(db_session: AsyncSession, scrap_product: Product):
    with pytest.raises(ValueError, match="greater than zero"):
        await record_scrap_inventory(
            db_session,
            product=scrap_product,
            quantity=0,
            event_type="scrap",
            reason="Invalid quantity",
        )
