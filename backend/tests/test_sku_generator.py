"""Regression tests for `generate_sku` (2026-05-12 prod 500).

Old implementation used COUNT(*) on the prefix to pick the next number,
which collided whenever the existing sequence had a gap. It also let
non-alphanumeric characters in the material name leak into the SKU
prefix, breaking the LIKE match and producing duplicates against
historically-spaced rows.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.material import Material
from app.models.product import Product
from app.services.inventory_service import _material_sku_code, generate_sku


def test_material_sku_code_strips_non_alphanumeric():
    assert _material_sku_code("SM Spool") == "SMSP"
    assert _material_sku_code("petg!@#") == "PETG"
    assert _material_sku_code("   ") == "UNKN"
    assert _material_sku_code(None) == "UNKN"


def test_material_sku_code_truncates_to_four():
    assert _material_sku_code("LongMaterialName") == "LONG"


@pytest.mark.asyncio
async def test_generate_sku_uses_max_not_count(db_session):
    """Existing rows: 0001, 0002, 0005 (gap at 3/4). COUNT-based logic
    would pick 0004 and collide eventually; MAX-based picks 0006."""
    m = Material(
        name="PLA", brand="X", spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"), net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    for suffix in ("0001", "0002", "0005"):
        db_session.add(Product(
            sku=f"PRD-PLA-{suffix}", name=f"P{suffix}", material_id=m.id,
            unit_cost=Decimal("1"), unit_price=Decimal("2"),
        ))
    await db_session.flush()

    next_sku = await generate_sku(db_session, m.id)
    assert next_sku == "PRD-PLA-0006"


@pytest.mark.asyncio
async def test_generate_sku_ignores_historical_spaced_prefix(db_session):
    """If old rows carry a space (legacy bug, e.g. PRD-SM M-0005), the
    new generator's space-stripped prefix shouldn't see them, so it
    starts a fresh sequence under the cleaned prefix."""
    m = Material(
        name="SM Spool", brand="X", spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"), net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    # Pre-seed legacy spaced SKUs.
    for suffix in ("0001", "0002", "0005"):
        db_session.add(Product(
            sku=f"PRD-SM M-{suffix}", name=f"L{suffix}", material_id=m.id,
            unit_cost=Decimal("1"), unit_price=Decimal("2"),
        ))
    await db_session.flush()

    next_sku = await generate_sku(db_session, m.id)
    # Cleaned prefix is PRD-SMSP-, no historical match -> starts at 0001.
    assert next_sku == "PRD-SMSP-0001"


@pytest.mark.asyncio
async def test_generate_sku_handles_empty_material_name(db_session):
    m = Material(
        name="!!!", brand="X", spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"), net_usable_g=Decimal("950"),
        cost_per_g=Decimal("0.02"),
    )
    db_session.add(m)
    await db_session.flush()
    sku = await generate_sku(db_session, m.id)
    assert sku == "PRD-UNKN-0001"


@pytest.mark.asyncio
async def test_generate_sku_unknown_material_returns_unkn_prefix(db_session):
    import uuid
    sku = await generate_sku(db_session, uuid.uuid4())
    assert sku.startswith("PRD-UNKN-")
