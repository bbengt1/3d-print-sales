# Inter-Account Transfers

Operators move money between two of the business's own bank accounts (checking → savings, Stripe payout → operating, etc.) as a first-class document instead of a manual journal entry. #246.

## Model

- **`InterAccountTransfer`** carries `from_account_id`, `to_account_id`, `amount`, `paid_on`, `received_on` (defaults to `paid_on`), and the resulting `journal_entry_id` for audit.
- **Always-posted**: a single JE with two journal lines is written on create. Each line carries an independent `posted_on` so each leg reconciles against the appropriate statement.
- **Same-currency only** in Phase 1.
- **Account pickers** restricted to `is_bank_account=True` (#239's typing).
- **`transfer_number`** allocator scope `inter_account_transfer` with format `T-{year}-{value:04d}`.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/banking/inter-account-transfers` | List, newest paid_on first. |
| `POST` | `/api/v1/banking/inter-account-transfers` | Create. Body: `from_account_id`, `to_account_id`, `amount`, `paid_on`, optional `received_on`, `notes`. |
| `GET` | `/api/v1/banking/inter-account-transfers/{id}` | Detail. |
| `DELETE` | `/api/v1/banking/inter-account-transfers/{id}` | Refused if either leg is reconciled. Voids the JE. |

## Edit lock

Delete fails when either leg's underlying journal line has `cleared_status='reconciled'` — uses the `assert_journal_line_editable` guard from #239. Reopen the relevant bank reconciliation first.

## Phase 2 follow-ups

- **Edit endpoint** (currently delete-and-recreate is the only path).
- **Cross-currency transfers** (depends on multi-currency Phase 1).
- **Auto-create from bank import** — add `create_inter_account_transfer` action to the rule registry from #241 once that lands.
- **Recurring transfers** (depends on the recurring-engine pattern in #247).
- **Frontend** — no banking UI exists yet.

## JE numbering note

Inter-account transfer JEs use the existing ad-hoc count-based JE numbering. Migrating JE numbering to the central allocator is part of #260's accounting-foundations cluster.
