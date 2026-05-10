# Bank Reconciliation

Operators reconcile a bank-typed GL account against a statement-end balance using a manual worksheet. Once finalized, the reconciled journal lines are locked from edits/deletes — preserving accounting integrity per #239.

## Concepts

- **Bank-typed account.** Any GL `Account` with `is_bank_account=True`. The kind dimension (`bank_account_kind`) is one of `checking`, `savings`, `credit_card`, `payment_processor`. Operators flag accounts via `PATCH /api/v1/banking/accounts/{id}/flag`.
- **Cleared status on journal lines.** `JournalLine.cleared_status` is one of:
  - `uncleared` — default, line has not been touched by any reconciliation.
  - `cleared` — included in an in-progress reconciliation. Lines flip back to `uncleared` if excluded before finalize.
  - `reconciled` — finalized in a reconciliation. **Edits and deletes are hard-blocked** until the reconciliation is reopened.
- **Reconciliation lifecycle.** `in_progress → finalized`. Admin can reopen a finalized recon back to `in_progress`, which flips its journal lines back to `cleared`.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/banking/accounts` | Lists bank-typed accounts with `running_balance`. |
| `PATCH` | `/api/v1/banking/accounts/{id}/flag` | Flag/unflag an account as a bank account. Body: `is_bank_account`, optional `bank_account_kind`. |
| `POST` | `/api/v1/banking/reconciliations` | Start a recon. Body: `account_id`, `statement_end_date`, `statement_ending_balance`, optional `notes`. |
| `GET` | `/api/v1/banking/reconciliations` | List recons (filter by `account_id`, `recon_status`). |
| `GET` | `/api/v1/banking/reconciliations/{id}` | Detail — eligible journal lines, included line ids, computed book balance, variance. |
| `PATCH` | `/api/v1/banking/reconciliations/{id}/toggle-line` | Include/exclude a journal line. Body: `journal_line_id`, `included` (bool). |
| `POST` | `/api/v1/banking/reconciliations/{id}/finalize` | Refuses if `book_balance != statement_ending_balance`. |
| `POST` | `/api/v1/banking/reconciliations/{id}/reopen` | Admin-only. Flips reconciled lines back to `cleared`. |

## Edit lock

`bank_reconciliation_service.assert_journal_line_editable(db, journal_line_id)` is the single guard call sites should use before mutating a journal line. It raises `JournalLineLockedError` (subclass of `BankReconciliationError`) when the line is reconciled — convert to a 409 at the API edge.

**#314 Phase 2 expanded coverage**: `reverse_journal_entry` now refuses to reverse any entry whose lines are in `reconciled` state (operator must reopen the recon first), and `finalize_reconciliation` refuses if `statement_end_date` falls on or before the configured period-close date.

## Period close (#314 Phase 2)

A simple global setting `accounting.period_close_date` (managed via `GET/PUT /api/v1/accounting/period-close-date`, admin-only) blocks JE-mutation paths from operating on or before that date. This complements the existing per-period `AccountingPeriod.status='locked'` mechanism — use the close-date for "books are sealed through Y-M-D"; use locked periods for finer-grained control.

Helpers in `accounting_service.py`:
- `get_period_close_date(db) -> date | None`
- `set_period_close_date(db, *, close_date)`
- `assert_financial_date_editable(db, *, target_date, ...)` — combined guard for both locked-periods and close-date.

Call sites that enforce the guard today:
- `accounting_service.create_journal_entry` (via `_validate_open_period` + `assert_financial_date_editable`)
- `accounting_service.reverse_journal_entry` (entry+reversal date) + reconciled-line check
- `bank_reconciliation_service.finalize_reconciliation` (statement_end_date)

## Phase 1 limitations / Phase 2 follow-ups (remaining)

Tracked in [#314](https://github.com/bbengt1/3d-print-sales/issues/314):

1. Audit and wire `assert_journal_line_editable` into invoice/bill/payment/credit-note void paths so each line touched by those mutations is checked individually (current coverage is the entry-level reconciled-line refusal in `reverse_journal_entry`).
2. Frontend admin surface for the period-close date setting (the accounting workspace has the slot but not the form yet).
3. Multi-currency (deferred to #319).
4. Statement import (#240 — landed) and auto-match rules (#241 — landed).
