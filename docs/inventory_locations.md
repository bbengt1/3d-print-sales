# Inventory Locations + Transfers (Phase 1)

Operators can model physical/logical inventory buckets (workshop, packaging, consignment, marketplace FBA) and record transfers between them. #245.

## Phase 1 scope (this PR)

- **`InventoryLocation` model + Default seed.** Migration creates the table and seeds a `Default` location so single-location operators see no behavior change.
- **`InventoryTransfer` + `InventoryTransferLine` models.** Lines accept material/supply/product kinds with quantity.
- **Transfer lifecycle**: `pending → in_transit (ship) → completed (receive)`. Cancellation allowed from `pending` or `in_transit`.
- **Allocator scope**: `inventory_transfer` registered with format `IT-{year}-{value:04d}` in #243's allocator.
- **No GL impact** — transfers are operational, not financial.
- **CRUD endpoints**: `/api/v1/inventory/locations`, `/api/v1/inventory/transfers`, plus `ship`, `receive`, `cancel`.

## Phase 2 follow-ups (deferred)

Each could be its own issue when prioritized:

1. **Per-location qty decrement.** Phase 1 records the transfer document but does not yet decrement source-side qty or increment destination-side qty in the existing inventory tracking. Material/supply/product on-hand stays in the global single-bucket model. Requires backfilling `material_receipt.location_id` and `inventory_transaction.location_id` on existing rows, plus rewiring consumption/sale paths to source from a chosen location.
2. **Sale-side fulfillment-from-location.** `Sale.fulfillment_location_id` (with channel-level default via `SalesChannel.default_fulfillment_location_id` and a global `default_fulfillment_location_id` setting). Auto-pick on marketplace orders.
3. **Soft-warn on negative stock** with a `prevent_negative_stock` settings toggle (default off).
4. **Frontend**: `/inventory/transfers` route + locations CRUD UI under `/admin`. Per-location qty column on inventory list pages.
5. **In-transit hold computation** — the available qty at a source location subtracts in-transit holds.
6. **Multi-location reorder points / min-stock thresholds.**
7. **Per-location physical addresses** (for shipping to/from).

## Allocator note

The `inventory_transfer` scope is now registered in `app.services.reference_number_service.FORMATS`. New scopes should follow the same pattern — one line in `FORMATS` and the parser will accept it everywhere.
