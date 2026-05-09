"""Inventory transfer lifecycle (#245 Phase 1).

Phase 1 covers location CRUD + the transfer state machine. It does not
yet wire decrement of source-side qty or increment of destination-side qty
into existing inventory tracking — material/supply/product on-hand stays
in the existing single-bucket model. The transfer document is persisted
and reportable, which is the operationally important step; making the
decrements per-location is Phase 2 (and requires the per-row backfill of
material_receipt.location_id and inventory_transaction.location_id that's
out of scope for this PR).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_location import (
    InventoryLocation,
    InventoryTransfer,
    InventoryTransferLine,
)
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


async def ship_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status != STATUS_PENDING:
        raise InventoryTransferError(f"Cannot ship transfer in status {transfer.status}")
    transfer.status = STATUS_IN_TRANSIT
    transfer.shipped_at = datetime.now(timezone.utc)
    await db.flush()
    return transfer


async def receive_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status != STATUS_IN_TRANSIT:
        raise InventoryTransferError(f"Cannot receive transfer in status {transfer.status}")
    transfer.status = STATUS_COMPLETED
    transfer.received_at = datetime.now(timezone.utc)
    await db.flush()
    return transfer


async def cancel_transfer(db: AsyncSession, transfer_id: uuid.UUID) -> InventoryTransfer:
    transfer = await _require_transfer(db, transfer_id)
    if transfer.status not in (STATUS_PENDING, STATUS_IN_TRANSIT):
        raise InventoryTransferError(f"Cannot cancel transfer in status {transfer.status}")
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
