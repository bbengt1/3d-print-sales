# Sales Orders + Purchase Orders (Phase 1)

#261 Phase 1. Optional intermediate documents between quote/PO-prequel and invoice/bill. Symmetric pair.

## Lifecycle

`draft → confirmed → cancelled` (or stays `confirmed` indefinitely until invoice/bill is generated separately).

Phase 1 does **not** track partial-fulfillment status (`partially_fulfilled`/`fulfilled`). The status flips manually via confirm/cancel actions.

## Models

- **`SalesOrder` + `SalesOrderLine`** — keyed by customer or customer_name; optional `quote_id` link for quote→SO conversion.
- **`PurchaseOrder` + `PurchaseOrderLine`** — keyed by `vendor_id` (required).

## Allocator scopes

- `sales_order` → `SO-{year}-{value:04d}`
- `purchase_order` → `PO-{year}-{value:04d}`

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/sales-orders` | Create (draft). |
| `GET` | `/api/v1/sales-orders` | List, filter by customer_id, status. |
| `GET` | `/api/v1/sales-orders/{id}` | Detail with lines. |
| `POST` | `/api/v1/sales-orders/{id}/confirm` | draft → confirmed. |
| `POST` | `/api/v1/sales-orders/{id}/cancel` | Any state → cancelled. |

Purchase orders mirror at `/api/v1/purchase-orders` with `vendor_id` instead of `customer_id`.

## Phase 2 follow-ups

- **Conversion endpoints**: `POST /sales-orders/{id}/create-invoice`, `POST /purchase-orders/{id}/create-bill` — pre-populate invoice/bill from SO/PO lines and link them.
- **Partial fulfillment** state machine: track invoice/bill generation against SO/PO lines, auto-advance status to `partially_fulfilled` / `fulfilled`.
- **Open backlog endpoints**: `GET /sales-orders/open` returning unfulfilled-line totals.
- **Email scope registration with #244** so SOs and POs can be emailed.
- **Goods receipt linkage** (`material_receipt.purchase_order_line_id`) for three-way matching.
- **Frontend** — no UI yet.
