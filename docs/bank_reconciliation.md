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

This guard is currently called only by the recon service itself. Phase 2 follow-up: wire it in to every endpoint that can edit or delete a journal line transitively (sale refunds, invoice voids, manual JE edits, etc.). Until then, downstream callers can corrupt a finalized reconciliation; the right pattern is to call `assert_journal_line_editable` for each affected line before saving.

## Phase 1 limitations / Phase 2 follow-ups

Each can be its own issue when prioritized:

1. **Wire the edit-lock guard into every journal-line mutation path** — sales refunds, invoice voids, manual JE edits, etc. (most important hardening step).
2. **Frontend `/banking` route** — accounts overview + reconciliation worksheet UI. None of these endpoints have a UI surface today.
3. **Period-close lock dates** — currently `accounting_period.py` doesn't gate `finalize_reconciliation`; if a recon is for a closed period the finalize succeeds. Worth tightening.
4. **Multi-currency** — Phase 1 assumes USD-only.
5. **Statement import** — picked up in #240 (depends on this issue's data model).
6. **Auto-match rules** — picked up in #241 (depends on #240).
