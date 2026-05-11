# Divisions + Projects

Two reporting dimensions for segmentation: a fixed cost center (`Division`) and a cross-cutting tag (`Project`). Phase 1 shipped the master data + CRUD; Phase 2 (#328) wired FKs across docs, the P&L by division/project filter, and the Job → Project rollup.

## Models

- **`Division`** — fixed cost center. A record has at most one. Use cases: Wholesale / Marketplace / Custom commissions.
- **`Project`** — cross-cutting tag, ad-hoc, time-bounded. Use cases: a specific custom commission, a launch, a one-off promo.

## Cross-table FKs

Optional `division_id` + `project_id` (both nullable) live on: `invoices`, `bills`, `sales`, `journal_entries`, `quotes`, `expense_claims`. `Job` carries an optional `project_id` only (no division — division is a cost-center concept that doesn't fit jobs).

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/divisions` | List active by default; `?include_inactive=true` for full. |
| `POST/PATCH/DELETE` | `/api/v1/divisions[/{id}]` | Standard CRUD; unique name. |
| `GET` | `/api/v1/projects` | List active by default; `?include_archived=true` for full. |
| `POST/PATCH/DELETE` | `/api/v1/projects[/{id}]` | Standard CRUD; status `active|archived`. |

## Reporting filters

`GET /api/v1/reports/profit-and-loss` accepts `division_id` and `project_id` query params. The filter threads through `_posted_journal_balances` so only journal entries tagged with the selected dimension(s) are aggregated.

## Phase 2 follow-ups (still deferred)

- **Cash-basis P&L filter** — division/project filter today applies to the accrual report only.
- **Per-division Balance Sheet** — same dimension threading on `/reports/balance-sheet`.
- **Sales report and Cash Flow** dimension filters.
- **Frontend** record-form pickers + report filter dropdowns.
