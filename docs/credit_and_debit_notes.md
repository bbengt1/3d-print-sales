# Credit + Debit Notes (Phase 1)

#248 Phase 1. Numbered customer-facing credit notes and vendor-facing debit notes with line items, JE on issue, apply-to-invoice/bill, void.

## Lifecycle

`draft → issued → partially_applied → applied` (or `void` from any non-applied state).

## Credit notes

- **Create**: draft with line items pointing at any account (typically Sales Returns 4800 or the original sale's revenue account).
- **Issue**: posts JE — Cr AR (1100) for total, Dr each line's account at line_total. Sets `status=issued`, links `journal_entry_id`.
- **Apply to invoice**: posts JE — Cr AR / Dr Sales Returns for the applied amount. Increments `applied_amount`, increments `Invoice.credits_applied`, decrements `Invoice.balance_due`. Status flips to `partially_applied` or `applied`.
- **Void**: refused if `applied_amount > 0`. Otherwise reverses the issue JE.

## Debit notes (symmetric)

- **Issue**: posts JE — Dr AP (2000) / Cr each line's account.
- **Apply to bill**: Dr AP / Cr Purchase Returns (5400).
- **Void**: same rules.

## Allocator scopes

- `credit_note` → `CN-{year}-{value:04d}`
- `debit_note` → `DN-{year}-{value:04d}`

## COA seed

Migration `20260509_19` adds:

| Code | Name | Type |
|---|---|---|
| 4800 | Sales Returns | revenue (debit-normal) |
| 5400 | Purchase Returns | cogs (credit-normal) |

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/credit-notes` | Create draft |
| `GET` | `/api/v1/credit-notes` | List, filter by `customer_id`, `status_filter` |
| `GET` | `/api/v1/credit-notes/{id}` | Detail with lines |
| `POST` | `/api/v1/credit-notes/{id}/issue` | Post JE |
| `POST` | `/api/v1/credit-notes/{id}/apply` | Body: `{target_id (invoice id), amount, applied_on?}` |
| `POST` | `/api/v1/credit-notes/{id}/void` | Reverse if unapplied |

Debit notes mirror: `/api/v1/debit-notes`, with `vendor_id` and `target_id` = bill id.

## Phase 2 follow-ups

- **Restock interaction with #242** — when a credit note line points at an inventory product, restore qty to its `FinishedGoodsLayer`. Requires the per-sale-line layer-draw breakdown that's also a #242 follow-up.
- **Refund-in-cash** — instead of holding the credit, post a cash refund (Cr Cash / Dr customer credit liability or AR depending on path).
- **Email scope registration with #244** — register `credit_note` and `debit_note` so notes can be emailed via the existing email transport.
- **Marketplace settlement bridging** — auto-create credit notes when marketplace refunds appear in settlements.
- **Tax line generation** on issue (currently subtotal == total).
- **Frontend** create/issue/apply UI plus invoice→credit-note pre-populate.
