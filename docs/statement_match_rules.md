# Statement Auto-Match Rules

Operators define rules that automatically handle imported statement lines (#241). The current shipped actions cover the full categorize-and-post workflow plus deeper AR/AP and inter-account-transfer routing (#316 Phase 2).

## Model

`StatementMatchRule`:

| Field | Notes |
|---|---|
| `name` | Operator label. |
| `account_id` | Optional; null = applies across all bank accounts. |
| `match_type` | `contains` (case-insensitive substring) or `regex` (Python re, case-insensitive). |
| `match_pattern` | Substring or regex. |
| `match_amount_sign` | `debit` (negative), `credit` (positive), or `any`. |
| `action` | One of the supported actions below. Validation rejects unknown values. |
| `priority` | Lower = higher priority. First match wins. |
| `is_active` | Inactive rules are skipped. |
| `category_account_id` | Required when `action = create_journal_entry`. |
| `customer_id` | Required when `action = create_receipt`. |
| `vendor_id` | Required when `action = create_payment`. |
| `transfer_to_account_id` | Required when `action = create_inter_account_transfer`. |
| `counterparty_name` | Optional descriptive label. |

## Supported actions

Rules are evaluated automatically during `import_statement` for every newly-inserted statement line, in priority order. The first matching rule's action runs.

| Action | Effect |
|---|---|
| `ignore` | Line's `match_status` flips to `ignored` so it never appears in the review queue. |
| `create_journal_entry` | Posts a balanced JE: Dr/Cr bank account vs `category_account_id` at the line's amount sign. Best for direct P&L hits (fees, interest income). |
| `create_receipt` | Posts Dr bank, Cr Accounts Receivable (1100). Creates a `Payment` row linked to `customer_id` with the full amount in `unapplied_amount` so the operator can later apply it to one or more invoices. Only fires on credit-sign lines. |
| `create_payment` | Posts Dr Accounts Payable (2000), Cr bank for vendor-paid outflows. No `BillPayment` row (we don't have an "unapplied BillPayment" concept yet); operator reconciles against bills manually. Only fires on debit-sign lines. |
| `create_inter_account_transfer` | Calls `inter_account_transfer_service.create_inter_account_transfer` with `from`/`to` derived from amount sign so each leg's `posted_on` lands on the correct statement. The own-side JE leg is linked back to the statement line for reconciliation. |

A rule whose target column is missing (e.g. `create_receipt` with `customer_id = null`) is counted in `skipped_unsupported_actions` rather than throwing; this lets operators stage a rule and fill in the target later.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/banking/rules` | List, ordered by priority. |
| `POST` | `/api/v1/banking/rules` | Create. Validates regex and per-action target requirements. |
| `PATCH` | `/api/v1/banking/rules/{id}` | Update. Re-validates on save. |
| `DELETE` | `/api/v1/banking/rules/{id}` | Hard delete. |
| `POST` | `/api/v1/banking/rules/imports/{import_id}/apply-rules` | Re-apply rules to existing pending lines on an import. Returns per-action counts. |
| `GET` | `/api/v1/banking/rules/imports/{import_id}/preview` | Dry-run: returns each pending line plus the rule that would fire (with a friendly `target` label) without mutating state. |
| `POST` | `/api/v1/banking/rules/from-line` | Create a starter rule from a staged statement line, pre-filling `match_pattern` and the sign from the line. Accepts optional `customer_id`, `vendor_id`, `transfer_to_account_id`, `category_account_id`. |

## Phase 2 follow-ups (still deferred)

1. **`BillPayment` integration** on `create_payment` so vendor outflows post against a specific bill (or to an "unapplied AP" bucket) instead of a raw JE.
2. **Frontend** rules CRUD + dry-run preview + reorder by priority.
3. **Tax-profile-aware rule actions** — apply a tax profile to the posted JE on category-style actions.
