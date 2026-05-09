from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.product import Product
from app.models.supply import Supply
from app.models.vendor import Vendor
from app.services.batch_ops_service import (
    BatchOpsError,
    batch_activate,
    batch_deactivate,
    batch_delete,
)


@pytest.mark.asyncio
async def test_unknown_scope_rejected(db_session):
    with pytest.raises(BatchOpsError):
        await batch_deactivate(db_session, scope="bogus", ids=[uuid.uuid4()])


@pytest.mark.asyncio
async def test_deactivate_vendors(db_session):
    vendors = [Vendor(name=f"Vendor {i}") for i in range(3)]
    for v in vendors:
        db_session.add(v)
    await db_session.flush()
    ids = [v.id for v in vendors]

    out = await batch_deactivate(db_session, scope="vendor", ids=ids)
    assert out["updated"] == 3
    assert out["errors"] == []

    refreshed = (await db_session.execute(select(Vendor).where(Vendor.id.in_(ids)))).scalars().all()
    assert all(v.is_active is False for v in refreshed)


@pytest.mark.asyncio
async def test_activate_brings_back(db_session):
    v = Vendor(name="ToBeReactivated", is_active=False)
    db_session.add(v)
    await db_session.flush()
    out = await batch_activate(db_session, scope="vendor", ids=[v.id])
    assert out["updated"] == 1
    refreshed = (await db_session.execute(select(Vendor).where(Vendor.id == v.id))).scalar_one()
    assert refreshed.is_active is True


@pytest.mark.asyncio
async def test_deactivate_unsupported_scope(db_session):
    with pytest.raises(BatchOpsError):
        # customer has no soft-deactivate field
        await batch_deactivate(db_session, scope="customer", ids=[uuid.uuid4()])


@pytest.mark.asyncio
async def test_deactivate_missing_ids_reported(db_session):
    real = Vendor(name="Real")
    db_session.add(real)
    await db_session.flush()
    fake = uuid.uuid4()
    out = await batch_deactivate(db_session, scope="vendor", ids=[real.id, fake])
    assert out["updated"] == 1
    assert len(out["errors"]) == 1
    assert out["errors"][0]["id"] == str(fake)


@pytest.mark.asyncio
async def test_delete_vendors(db_session):
    vs = [Vendor(name=f"Del{i}") for i in range(3)]
    for v in vs:
        db_session.add(v)
    await db_session.flush()
    ids = [v.id for v in vs]
    out = await batch_delete(db_session, scope="vendor", ids=ids)
    assert out["deleted"] == 3
    refreshed = (await db_session.execute(select(Vendor).where(Vendor.id.in_(ids)))).scalars().all()
    assert refreshed == []


@pytest.mark.asyncio
async def test_supply_uses_active_field(db_session):
    s = Supply(name="Box", unit="each", unit_cost=Decimal("1"), quantity_on_hand=Decimal("10"), reorder_point=Decimal("5"))
    db_session.add(s)
    await db_session.flush()
    out = await batch_deactivate(db_session, scope="supply", ids=[s.id])
    assert out["updated"] == 1
    refreshed = (await db_session.execute(select(Supply).where(Supply.id == s.id))).scalar_one()
    assert refreshed.active is False
