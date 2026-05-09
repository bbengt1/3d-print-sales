# Reference Number Allocator

Race-safe, single-source allocator for human-readable record numbers. Backs `sale_number`, `invoice_number`, `quote_number`, and (over time) any other numbered document we add. Closes the `sale_number` race historically called out in `agents.md` Known Risks.

## Service contract

```python
from app.services.reference_number_service import next_number

# Inside the same transaction that inserts the parent record:
sale.sale_number = await next_number(session, "sale")
```

`next_number(session, scope, year=None) -> str` atomically:

1. Increments `reference_sequences.last_value` for `(scope, year)` (defaults to `date.today().year`).
2. Formats the result via the per-scope `FORMATS[scope]` template.
3. Returns the canonical string.

On PostgreSQL the increment is one statement (`INSERT ... ON CONFLICT DO UPDATE ... RETURNING`). On SQLite (the test path) it falls back to select-then-update.

## Skipped numbers are intentional

When the outer transaction rolls back after `next_number` ran, the increment also rolls back, so the **next call returns the same value** — accountants consider this a feature because it keeps numbers contiguous across successful posts. If a record creation fails *after* commit (e.g. an HTTP error reaches the client mid-response), the number is "burned" and the next allocation skips ahead. Documented behavior. Don't try to reuse skipped numbers.

## Registered scopes (today)

| Scope | Format | Example | Caller |
|---|---|---|---|
| `sale` | `S-{year}-{value:04d}` | `S-2026-0123` | `sales_service.generate_sale_number` |
| `invoice` | `INV-{year}-{value:04d}` | `INV-2026-0042` | `invoices.create_invoice` (when `invoice_number` is null/blank) |
| `quote` | `Q-{year}-{value:04d}` | `Q-2026-0007` | `quotes.create_quote` (when `quote_number` is null/blank) |

## Adding a scope

1. Add the format string to `FORMATS` in `backend/app/services/reference_number_service.py`.
2. (Optional) Add a regex to `_PARSE_PATTERNS` if a backfill migration needs to seed historical values.
3. Call `await next_number(session, "<your_scope>")` from the relevant create path.

That's it — no model change, no migration, the existing `reference_sequences` table holds all scopes.

## Manual / operator-supplied numbers

Invoices and quotes accept an operator-supplied `invoice_number` / `quote_number` in the request body. When supplied, the allocator is **not** consulted — the existing uniqueness check on the parent table guards against collisions. When the field is null or blank, the allocator fills it in. Sales numbers are always allocator-generated.

## Backfill on migration

The `20260509_01_add_reference_sequences` migration parses every existing `sale_number`, `invoice_number`, `quote_number` against the canonical pattern. For each `(scope, year)` it seeds `last_value = max(parsed numeric suffix)`. Records with non-canonical numbers (e.g. an operator-supplied `CUST-PROJECT-7`) don't match the pattern and are simply ignored — they continue to coexist with the allocator.
