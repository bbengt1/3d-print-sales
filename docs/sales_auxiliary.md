# Sales Auxiliary

#263 Phase 1 ships **delivery notes** only. The other three pieces of the original scope (late payment fees, billable expenses, withholding tax for direct customers) remain ❌ as separate sub-features and can be opened as follow-up issues when prioritized.

## Delivery notes

Numbered dispatch document, separate from the invoice. Tracks shipped-quantity per line so partial dispatches against a single invoice are visible.

### Lifecycle

`draft → shipped → delivered → cancelled` (operator-driven; no auto state machine).

### Allocator

Scope `delivery_note` with format `DLV-{year}-{value:04d}` (avoiding collision with `DN-` for debit notes).

### Model

- **`DeliveryNote`** — optional `invoice_id` link (a delivery note can stand alone or attach to an invoice), `customer_id` or `customer_name`, `issued_on`, `shipped_on`, `tracking_number`, `status`.
- **`DeliveryNoteLine`** — `description`, `quantity`, optional per-line `notes`.

No GL impact — purely operational.

### API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/delivery-notes` | Create draft. Requires invoice_id, customer_id, or customer_name. |
| `GET` | `/api/v1/delivery-notes` | List, filter by invoice_id, status. |
| `GET` | `/api/v1/delivery-notes/{id}` | Detail with lines. |
| `PATCH` | `/api/v1/delivery-notes/{id}` | Update status, shipped_on, tracking_number, notes. |
| `DELETE` | `/api/v1/delivery-notes/{id}` | Only allowed in `draft` state. |

## Phase 2 follow-ups (still ❌)

Each can become its own issue:

1. **Late payment fees** — per-customer `late_payment_fee_rate_pct` + grace days; cron auto-generates fee invoices on overdue threshold.
2. **Billable expenses** — bill-line → customer pass-through with optional markup.
3. **Withholding tax for direct customers** — generalize the marketplace-settlement withholding pattern via a `WithholdingProfile` on Customer.
4. **Email delivery notes** via #244 — register `delivery_note` scope.
5. **Frontend** for the delivery-note flow.
