# Batch Operations (Phase 1)

#254 Phase 1. Bulk deactivate / activate / hard-delete on master-data
records. CSV import deferred to Phase 2.

## Supported scopes

| Scope | Soft-deactivate field |
|---|---|
| `vendor` | `is_active` |
| `product` | `is_active` |
| `supply` | `active` |
| `customer` | (no flag — delete only) |
| `material` | (no flag — delete only) |

`GET /api/v1/batch/scopes` returns this list with the `deactivatable` flag.

Transactions (sale, invoice, bill, JE, etc.) are intentionally excluded — bulk modification is too risky given ledger side-effects.

## API

| Verb | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/batch/{scope}/deactivate` | Body: `{ids: [...]}`. Refuses if scope has no active field. Per-row error reporting. |
| `POST` | `/api/v1/batch/{scope}/activate` | Reactivate. Same shape. |
| `POST` | `/api/v1/batch/{scope}/delete` | Hard delete. FK violations caught per-row so partial success is reported. |
| `GET` | `/api/v1/batch/scopes` | List supported scopes + their soft-deactivate availability. |

Max 500 ids per request.

## Phase 2 follow-ups

- **CSV import** for bulk create per scope, with column-mapping UI.
- **Frontend** row multi-select on list pages + batch dropdown.
- **Excel format** (currently CSV-only thinking).
- **Undo** of a completed batch.
- **Audit-log** rows per affected record (currently service-level only — no audit trail per row).
