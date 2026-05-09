from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inventory_location import InventoryLocation, InventoryTransfer
from app.services.inventory_transfer_service import (
    InventoryTransferError,
    cancel_transfer,
    create_transfer,
    ensure_default_location,
    receive_transfer,
    ship_transfer,
)


async def _two_locations(db_session):
    a = await ensure_default_location(db_session)
    b = InventoryLocation(name="Workshop B", kind="internal")
    db_session.add(b)
    await db_session.flush()
    return a, b


@pytest.mark.asyncio
async def test_create_transfer_happy_path(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "material_id": None, "quantity": Decimal("5")}],
    )
    assert t.transfer_number.startswith("IT-")
    assert t.status == "pending"


@pytest.mark.asyncio
async def test_create_transfer_same_locations_rejected(db_session):
    a, _ = await _two_locations(db_session)
    with pytest.raises(InventoryTransferError):
        await create_transfer(
            db_session,
            from_location_id=a.id,
            to_location_id=a.id,
            lines=[{"kind": "material", "quantity": Decimal("1")}],
        )


@pytest.mark.asyncio
async def test_create_transfer_no_lines_rejected(db_session):
    a, b = await _two_locations(db_session)
    with pytest.raises(InventoryTransferError):
        await create_transfer(db_session, from_location_id=a.id, to_location_id=b.id, lines=[])


@pytest.mark.asyncio
async def test_create_transfer_zero_qty_rejected(db_session):
    a, b = await _two_locations(db_session)
    with pytest.raises(InventoryTransferError):
        await create_transfer(
            db_session,
            from_location_id=a.id,
            to_location_id=b.id,
            lines=[{"kind": "material", "quantity": Decimal("0")}],
        )


@pytest.mark.asyncio
async def test_full_lifecycle(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "quantity": Decimal("3")}],
    )
    t = await ship_transfer(db_session, t.id)
    assert t.status == "in_transit"
    assert t.shipped_at is not None
    t = await receive_transfer(db_session, t.id)
    assert t.status == "completed"
    assert t.received_at is not None


@pytest.mark.asyncio
async def test_cannot_ship_already_shipped(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "quantity": Decimal("1")}],
    )
    await ship_transfer(db_session, t.id)
    with pytest.raises(InventoryTransferError):
        await ship_transfer(db_session, t.id)


@pytest.mark.asyncio
async def test_cancel_from_pending(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "quantity": Decimal("1")}],
    )
    t = await cancel_transfer(db_session, t.id)
    assert t.status == "cancelled"
    assert t.cancelled_at is not None


@pytest.mark.asyncio
async def test_cancel_from_in_transit(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "quantity": Decimal("1")}],
    )
    await ship_transfer(db_session, t.id)
    t = await cancel_transfer(db_session, t.id)
    assert t.status == "cancelled"


@pytest.mark.asyncio
async def test_cannot_cancel_completed(db_session):
    a, b = await _two_locations(db_session)
    t = await create_transfer(
        db_session,
        from_location_id=a.id,
        to_location_id=b.id,
        lines=[{"kind": "material", "quantity": Decimal("1")}],
    )
    await ship_transfer(db_session, t.id)
    await receive_transfer(db_session, t.id)
    with pytest.raises(InventoryTransferError):
        await cancel_transfer(db_session, t.id)


@pytest.mark.asyncio
async def test_ensure_default_location_idempotent(db_session):
    a = await ensure_default_location(db_session)
    b = await ensure_default_location(db_session)
    assert a.id == b.id
    rows = (await db_session.execute(select(InventoryLocation).where(InventoryLocation.name == "Default"))).scalars().all()
    assert len(rows) == 1
