# Production Orders (Phase 1)

#242 Phase 1. Closes the loop between operational job tracking and inventory accounting: a closed production order FIFO-consumes materials from `material_receipts`, posts a balanced JE Cr Material Inventory / Dr Finished Goods Inventory, and creates a `FinishedGoodsLayer` row for the produced units.

## Lifecycle

`planned → completed` (or `cancelled` from planned).

## Models

- **`ProductionOrder`** — order_number (PRD-{year}-{value:04d} via #243), product, output quantity, status, completion timestamp, totals, JE link.
- **`ProductionOrderConsumption`** — one row per BOM line, snapshotted at order create time so later BOM edits don't change historical orders. Phase 1 stores `actual_qty` = `planned_qty` (no operator editor yet) and only material kinds drive cost.
- **`FinishedGoodsLayer`** — one row per closed order's output. Carries `qty_total`, `qty_remaining`, `unit_cost`. **Read-only in Phase 1** — Phase 2 will FIFO-draw from these on the sales-side COGS path.

## Close-out flow

1. For each `material` consumption row: FIFO-draw from `material_receipts.quantity_remaining_g` matching `inventory_accounting_service.consume_material_receipts_for_job`. Uses `landed_cost_per_g` when set, else `unit_cost_per_g`.
2. Total material cost = sum of FIFO-drawn costs.
3. Applied overhead = 0 (Phase 1 has no overhead-rate setting).
4. Total finished-goods value = material cost + overhead.
5. If value > 0: post JE — Dr Finished Goods Inventory (1400), Cr Raw Materials Inventory (1200).
6. Create one `FinishedGoodsLayer` at unit_cost = value / output_qty.
7. Status → `completed`, stamp `completed_at`, link the JE.

When `total_finished_goods_value == 0` (e.g., product with no BOM, or material receipts already drained to 0), the layer is still created with unit_cost=0 but no JE is posted — a useful starting-balance shortcut.

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/production-orders` | Create planned order with BOM snapshot. |
| `GET` | `/api/v1/production-orders` | List, filter `?status_filter=...`. |
| `GET` | `/api/v1/production-orders/{id}` | Detail with consumption rows. |
| `POST` | `/api/v1/production-orders/{id}/close` | FIFO-consume + post JE + create layer. |
| `POST` | `/api/v1/production-orders/{id}/cancel` | Cancel a planned order (no GL impact). |
| `GET` | `/api/v1/production-orders/finished-goods/{product_id}` | List FinishedGoodsLayer rows for a product. `?only_remaining=false` to include drained layers. |

## Phase 2 follow-ups

The big one: **Sales-side COGS rewrite.** When a sale's product has any `FinishedGoodsLayer` with `qty_remaining > 0`, COGS for that line draws FIFO from the layers; otherwise falls back to `cost_calculator.py`. This is the highest-risk behavior shift in the original #242 scope and was deliberately deferred to Phase 1 to keep the production-order document landable cleanly. Wiring it requires:
- Per-sale-line audit of which layers were drawn (stored as JSONB on `sale_item.py`) so refunds can restore qty_remaining.
- Mixed-mode handling when line qty exceeds remaining layer qty (split between layers + cost_calculator residual).
- Audit-log entry per COGS post recording which path was used.

Other Phase 2 items:
- Operator-editable `actual_qty` on consumption rows at close-out (currently uses `planned_qty` as-is).
- Hourly overhead applied at close-out (`overhead_rate_per_hour` setting × actual print hours from a future Job link).
- Optional `job_production_order_id` link on `Job` for hour rollup.
- Supply consumption FIFO (snapshotted but not consumed in Phase 1).
- Variance accounting (favorable/unfavorable BOM-vs-actual variances) — out of scope per #242 design.
- Frontend `/production` route.
