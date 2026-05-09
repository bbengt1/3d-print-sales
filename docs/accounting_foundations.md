# Accounting Foundations Cluster

Three small but useful pieces from the §7 gap rows, all in one PR. #260.

## 1. Recurring journal entries

Mirror of [docs/recurring_invoices.md](recurring_invoices.md) but for JEs. Cron-driven via `/api/v1/accounting/recurring-journal-entries/run-due`. Useful for monthly accruals (rent, software subscriptions billed via AP, etc.).

- Same cadence math (daily / weekly / monthly / yearly with day-of-month + leap-day edge cases) — reuses `recurring_invoice_service.advance_date`.
- Lines template is JSONB with `{account_id, entry_type, amount, description}`. Validated to balance (debits = credits) on create + edit.
- Lifecycle mirrors `recurring_invoice`: `run_one` advances on success, holds on failure; `skip_next` advances without generating; `run_due` is idempotent within a day on success.

## 2. Suspense report

Operators occasionally need a "fix-me bucket" — when an automated import / sync isn't sure where to post. Manager.io models this as an account. We seed `1900 Suspense` (asset, debit-normal) into the COA and expose a drill-down via:

- `GET /api/v1/accounting/suspense` — returns the account balance plus every journal line currently posting to it (with the source transaction's id, number, date, memo). Operators reclassify by editing the source transaction.

Phase 2 follow-up: a "reclassify" inline action that creates a balancing journal entry to move the amount out of suspense — currently handled by editing the source transaction.

## 3. Starting balances workflow

For migrating an existing business onto this app at a chosen go-live date, we need to seed opening balances on every relevant account. The endpoint posts a single balanced JE:

- `POST /api/v1/accounting/starting-balances` — admin-only. Body: `{ as_of, balances: [{account_id, amount}], force? }`.
- `amount` is interpreted on the account's natural side: a debit-normal asset with `amount=5000` posts `Dr 5000`. The balancing entry uses **`3300 Opening Balance Equity`** (also seeded by this issue's migration).
- **Activity guard**: refuses if any of the named accounts already have journal lines, unless `force=true`. Document the override in your migration runbook.

## COA seed

Migration `20260509_13` adds:

| Code | Name | Type |
|---|---|---|
| 1900 | Suspense | asset (debit-normal) |
| 3300 | Opening Balance Equity | equity (credit-normal) |

Idempotent — re-running against an existing install is a no-op.

## Phase 2 follow-ups

- **Verify-and-document audit** for the §7 🔁 rows (account-code display, custom control accounts, special accounts, period-close lock-date enforcement) — deferred from this issue's scope.
- **n8n workflow JSON** for the daily `recurring-journal-entries-daily` cron (mirror of the deploy workflow pattern).
- **Suspense reclassify** inline action.
- **Starting balances CSV import** for onboarding from another accounting tool.
- **Frontend** — no UI for any of these three today.
