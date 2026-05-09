# Divisions + Projects (Phase 1)

Two reporting dimensions for segmentation. Phase 1 ships the master data + CRUD; cross-table FK additions on bills/invoices/sales/journal_entries deferred to Phase 2.

## Models

- **`Division`** — fixed cost center. A record has at most one. Use cases: Wholesale / Marketplace / Custom commissions.
- **`Project`** — cross-cutting tag, ad-hoc, time-bounded. Use cases: a specific custom commission, a launch, a one-off promo.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/divisions` | List active by default; `?include_inactive=true` for full. |
| `POST/PATCH/DELETE` | `/api/v1/divisions[/{id}]` | Standard CRUD; unique name. |
| `GET` | `/api/v1/projects` | List active by default; `?include_archived=true` for full. |
| `POST/PATCH/DELETE` | `/api/v1/projects[/{id}]` | Standard CRUD; status `active|archived`. |

## Phase 2 follow-ups

- **Optional FKs** (`division_id`, `project_id`) on `bill`, `invoice`, `sale`, `journal_entry`, `expense_claim`, `quote`. Each nullable.
- **Job link** to project (`Job.project_id` — one-way, optional).
- **Report filtering** by division and by project on P&L, Balance Sheet (#249), Sales report, Cash Flow.
- **Frontend** master-data CRUD + record-form pickers + report filter dropdowns.
