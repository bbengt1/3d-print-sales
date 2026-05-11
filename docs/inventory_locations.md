# Inventory Locations + Transfers

Operators model physical/logical inventory buckets (workshop, packaging, consignment, marketplace FBA) and record transfers between them. Originally #245 (Phase 1); per-location stock + fulfillment routing extended in #318 (Phase 2).

## Phase 1 — locations + transfer document

- **`InventoryLocation` model + Default seed.** A `Default` location is auto-seeded so single-location operators see no behavior change.
- **`InventoryTransfer` + `InventoryTransferLine` models.** Lines accept material/supply/product kinds with quantity.
- **Transfer lifecycle**: `pending → in_transit (ship) → completed (receive)`. Cancellation allowed from `pending` or `in_transit`.
- **Allocator scope**: `inventory_transfer` registered with format `IT-{year}-{value:04d}` in #243's allocator.
- **No GL impact** — transfers are operational, not financial.
- **CRUD endpoints**: `/api/v1/inventory/locations`, `/api/v1/inventory/transfers`, plus `ship`, `receive`, `cancel`.

## Phase 2 — per-location stock SoT + sale fulfillment routing

### `ProductLocationStock` — source of truth

- New table `product_location_stock` keys `(product_id, location_id)` and holds the `on_hand_qty` for that pair.
- `Product.stock_qty` is kept in sync as the aggregate sum across locations so existing single-bucket reads keep working.
- Migration `20260511_01_product_location_stock.py` backfills each product's existing `stock_qty` to the seeded `Default` location.

### Movement rules

| Event | Source on-hand | Destination on-hand |
| --- | --- | --- |
| Transfer **ship** | decrements immediately | unchanged (in-transit only) |
| Transfer **receive** | unchanged | increments |
| Transfer **cancel** while `in_transit` | restored | unchanged |
| Transfer **cancel** while `pending` | unchanged | unchanged |
| Sale fulfillment | decrements resolved fulfillment location | — |
| Refund / cancel | restored to original fulfillment location | — |

`in_transit_to_qty` is computed live from `inventory_transfer_lines` joined to transfers in `in_transit` status; it is never stored as a separate hold.

### Fulfillment location resolution

`product_location_stock_service.resolve_fulfillment_location_id` returns, in order:

1. `Sale.fulfillment_location_id` if set.
2. Setting `inventory.default_fulfillment_location_id` (managed via `PUT /api/v1/inventory/default-fulfillment-location`).
3. The auto-seeded `Default` location (created on demand).

### Negative-stock policy

- **Soft-warn (default).** Decrements that drive projected on-hand below zero return a `StockWarning` record from `pls.adjust`; callers may surface it. Sales still complete.
- **Hard-block.** Setting `inventory.prevent_negative_stock = "true"` (managed via `PUT /api/v1/inventory/prevent-negative-stock`) turns the same condition into `NegativeStockBlockedError`. Sales routes raise that as the existing `InsufficientStockError`, so the route layer needs no change.

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/inventory/locations/{id}/product-stock` | Per-product on-hand + in-transit-to + projected at this location (SoT). |
| GET | `/api/v1/inventory/locations/{id}/stock-snapshot` | Back-compat snapshot derived from completed transfers (Phase 1). |
| GET / PUT | `/api/v1/inventory/default-fulfillment-location` | Read/set the fallback fulfillment location. |
| GET / PUT | `/api/v1/inventory/prevent-negative-stock` | Read/set the hard-block toggle. |

## Phase 2 follow-ups (still deferred)

- **Materials / supplies per-location SoT.** Transfer documents already carry material/supply lines, but only product lines feed `ProductLocationStock`. Material consumption stays single-bucket until this lands.
- **Frontend.** Multi-location surfaces (`/inventory/transfers` UI, per-location qty column on inventory list pages, fulfillment-location picker on sale form) — backend is ready; UI is a follow-up.
- **Multi-location reorder points / min-stock thresholds.**
- **Per-location physical addresses** (for shipping to/from).
- **Channel-level default fulfillment location** (`SalesChannel.default_fulfillment_location_id`) — currently the only fallback is the global setting.

## Allocator note

The `inventory_transfer` scope is registered in `app.services.reference_number_service.FORMATS`. New scopes follow the same pattern — one line in `FORMATS` and the parser accepts it everywhere.
