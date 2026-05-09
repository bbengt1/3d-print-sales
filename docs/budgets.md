# Per-Account Monthly Budgets

#259 Phase 1. Per-account monthly budget table — operators set planned amounts and (in Phase 2) the P&L gains a budget column showing actual vs. planned.

## Model

`AccountBudget`: one row per `(account_id, year, month)`. Unique constraint enforces "one budget per cell." Amounts are stored as `Numeric(14, 2)`.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/budgets?year=...&account_id=...` | List, filterable. |
| `POST` | `/api/v1/budgets/upsert` | Bulk upsert per `(account, year, month)`. Refuses balance-sheet accounts (only income/cogs/expense). |
| `DELETE` | `/api/v1/budgets/{id}` | Delete a single row. |
| `POST` | `/api/v1/budgets/copy-year?from_year=...&to_year=...` | Idempotent copy — skips cells already filled in `to_year`. |

## Phase 2 follow-ups

- **P&L "Budget" column** toggle showing planned + actual + variance ($ and %).
- **Frontend** grid editor: rows = accounts × columns = months, inline-editable.
- **CSV import** for bulk seeding.
- **Per-division / per-project budgets** (depends on #255 cross-table FKs).
- **Custom report builder** (explicitly deferred from this issue's scope; will be a separate scoping conversation).
