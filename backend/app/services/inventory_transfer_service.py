"""Inventory transfer lifecycle (#245 Phase 1 → #318 Phase 2).

Phase 1 added the state machine without touching per-location stock.
Phase 2 wires product lines through ``product_location_stock_service``:
shipping decrements source on-hand, receiving increments destination
on-hand, and cancelling while in-transit restores the source.

Material and supply lines still flow through the document only; their
per-location SoT is a separate follow-up.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_location import (
    InventoryLocation,
    InventoryTransfer,
    InventoryTransferLine,
)
from app.services import product_location_stock_service as pls
from app.services.reference_number_service import next_number


class InventoryTransferError(RuntimeError):
    pass


STATUS_PENDING = "pending"
STATUS_IN_TRANSIT = "in_transit"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"


async def ensure_default_location(db: AsyncSession) -> InventoryLocation:
    row = (
        await db.execute(select(InventoryLocation).where(InventoryLocation.name == "Default"))
    ).scalar_one_or_none()
    if row:
        return row
    row = InventoryLocation(name="Default", kind="internal")
    db.add(row)
    await db.flush()
    return row


async def create_transfer(
    db: AsyncSession,
    *,
    from_location_id: uuid.UUID,
    to_location_id: uuid.UUID,
    lines: list[dict],
    transferred_by_user_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> InventoryTransfer:
    if from_location_id == to_location_id:
        raise InventoryTransferError("from_location and to_location must differ")
    if not lines:
        raise InventoryTransferError("transfer must have at least one line")

    number = await next_number(db, "inventory_transfer")
    transfer = InventoryTransfer(
        transfer_number=number,
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        status=STATUS_PENDING,
        transferred_by_user_id=transferred_by_user_id,
        notes=notes,
    )
    db.add(transfer)
    await db.flush()

    for line in lines:
        kind = line["kind"]
        if kind not in ("material", "supply", "product"):
            raise InventoryTransferError(f"Unknown line kind: {kind!r}")
        if line.get("quantity", 0) <= 0:
            raise InventoryTransferError("Line quantity must be > 0")
        db.add(
            InventoryTransferLine(
                transfer_id=transfer.id,
                kind=kind,
                material_id=line.get("material_id") if kind == "material" else None,
                supply_id=line.get("supply_id") if kind == "supply" else None,
                product_id=line.get("product_id") if kind == "product" else None,
                quantity=line["quantity"],
            )
        )
    await db.flush()
    return transfer


async def _product_lines(db: AsyncSession, transfer_id: uuid.UUID) -> list[InventoryTransferLine]:
    return (
        (
            await db.execute(
                select(InventoryTransferLine).where(
                    InventoryTransferLine.transfer_id == transfer_id,
                    InventoryTransferLine.kind == "product",
                )
            )
        )
        .scalars()
        .all()
    )


async def ship_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status != STATUS_PENDING:
        raise InventoryTransferError(f"Cannot ship transfer in status {transfer.status}")

    for line in await _product_lines(db, transfer.id):
        if not line.product_id:
            continue
        await pls.adjust(
            db,
            product_id=line.product_id,
            location_id=transfer.from_location_id,
            delta=-Decimal(line.quantity),
        )

    transfer.status = STATUS_IN_TRANSIT
    transfer.shipped_at = datetime.now(timezone.utc)
    await db.flush()
    return transfer


async def receive_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status != STATUS_IN_TRANSIT:
        raise InventoryTransferError(f"Cannot receive transfer in status {transfer.status}")

    for line in await _product_lines(db, transfer.id):
        if not line.product_id:
            continue
        await pls.adjust(
            db,
            product_id=line.product_id,
            location_id=transfer.to_location_id,
            delta=Decimal(line.quantity),
        )

    transfer.status = STATUS_COMPLETED
    transfer.received_at = datetime.now(timezone.utc)
    await db.flush()
    return transfer


async def cancel_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status not in (STATUS_PENDING, STATUS_IN_TRANSIT):
        raise InventoryTransferError(f"Cannot cancel transfer in status {transfer.status}")

    if transfer.status == STATUS_IN_TRANSIT:
        # Release the source-side hold that ship_transfer applied.
        for line in await _product_lines(db, transfer.id):
            if not line.product_id:
                continue
            await pls.adjust(
                db,
                product_id=line.product_id,
                location_id=transfer.from_location_id,
                delta=Decimal(line.quantity),
            )

    transfer.status = STATUS_CANCELLED
    transfer.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    return transfer


async def _require_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = (
        await db.execute(select(InventoryTransfer).where(InventoryTransfer.id == transfer_id))
    ).scalar_one_or_none()
    if not transfer:
        raise InventoryTransferError("Transfer not found")
    return transfer
