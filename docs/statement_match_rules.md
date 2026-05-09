# Statement Auto-Match Rules (Phase 1)

Operators define rules that automatically handle imported statement lines (#241). Phase 1 supports the **`ignore`** action only — auto-skip noise like ATM fees from review. Phase 2 will add `create_receipt` / `create_payment` actions that auto-post journal entries.

## Model

`StatementMatchRule`:

| Field | Notes |
|---|---|
| `name` | Operator label. |
| `account_id` | Optional; null = applies across all bank accounts. |
| `match_type` | `contains` (case-insensitive substring) or `regex` (Python re, case-insensitive). |
| `match_pattern` | Substring or regex. |
| `match_amount_sign` | `debit` (negative), `credit` (positive), or `any`. |
| `action` | `ignore` (Phase 1). Validation rejects unsupported actions. |
| `priority` | Lower = higher priority. First match wins. |
| `is_active` | Inactive rules are skipped. |

## Behavior

Rules are evaluated automatically during `import_statement` for every newly-inserted statement line, in priority order. The first matching rule's action runs:

- **`ignore`** → line's `match_status` flips to `ignored` so it never appears in the review queue.
- Other actions → silently no-op in Phase 1, counted in `skipped_unsupported_actions`.

The `apply-rules` endpoint can be called manually to re-evaluate an existing import's pending lines after rules change.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/banking/rules` | List, ordered by priority. |
| `POST` | `/api/v1/banking/rules` | Create. Validates regex if `match_type=regex`; rejects unsupported actions. |
| `PATCH` | `/api/v1/banking/rules/{id}` | Update. Re-validates on save. |
| `DELETE` | `/api/v1/banking/rules/{id}` | Hard delete. |
| `POST` | `/api/v1/banking/rules/imports/{import_id}/apply-rules` | Re-apply rules to existing pending lines on an import. |

## Phase 2 follow-ups

1. **`create_receipt` / `create_payment` actions** — auto-post a JE with the matching counterparty + category accounts. Requires populating `counterparty_id`, `category_account_id`, `tax_profile_id` fields on the rule.
2. **Dry-run preview** — run rules against an import without mutating, return per-rule counts so operators can validate before activation.
3. **"Create rule from line" shortcut** — pre-fill match_pattern from the description.
4. **`create_inter_account_transfer` action** — paired with #246 once both ship.
5. **Frontend** rules CRUD + dry-run preview + reorder by priority.
