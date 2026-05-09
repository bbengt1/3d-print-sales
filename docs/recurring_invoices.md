# Recurring Sales Invoices

Operators schedule a sales invoice to auto-generate on a cadence — monthly retainer, weekly consignment statement, quarterly maintenance contract, etc. Cron-driven via the same n8n pattern used elsewhere. #247.

## Model

- **`RecurringInvoice`** — the rule. Carries customer, cadence, snapshot `line_items_template` (JSONB), `next_run_on`, optional `end_on`, audit fields (`last_error`, `last_failed_at`).
- **`RecurringInvoiceRun`** — one row per cron / manual run, linking the generated invoice (or recording the failure / skip).

## Cadence math

| Cadence | Behavior |
|---|---|
| `daily` + `interval_count=N` | add N days |
| `weekly` + `interval_count=N` | add N×7 days |
| `monthly` + `interval_count=N` | add N months, preserving day-of-month with month-end clamp (Jan 31 → Feb 28/29) |
| `yearly` + `interval_count=N` | add N years, with Feb 29 → Feb 28 in non-leap years |

## Lifecycle

- `start_on` is the first scheduled run; `next_run_on` defaults to it on create.
- `run_one` succeeds → invoice created (using #243's allocator for the number) → schedule advances. Fails → schedule does **not** advance, `last_error` is recorded.
- `skip_next` advances without generating an invoice.
- `run_due` (cron) picks up every active rule with `next_run_on <= today` and runs each. **Idempotent within a day** on success: a second call finds nothing further due.
- When `next_run_on > end_on` after an advance, `is_active` flips false automatically.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/recurring-invoices` | Filter `?active_only=true`. |
| `POST` | `/api/v1/recurring-invoices` | Create. |
| `GET` | `/api/v1/recurring-invoices/{id}` | Detail. |
| `PATCH` | `/api/v1/recurring-invoices/{id}` | Edit (template + cadence + state). |
| `DELETE` | `/api/v1/recurring-invoices/{id}` | Hard delete. |
| `POST` | `/api/v1/recurring-invoices/{id}/run-now` | Generate one immediately. |
| `POST` | `/api/v1/recurring-invoices/{id}/skip-next` | Advance without generating. |
| `POST` | `/api/v1/recurring-invoices/run-due` | Cron entry point. |
| `GET` | `/api/v1/recurring-invoices/{id}/runs` | Run history. |

## Cron wiring (operator runbook)

Set up a daily n8n workflow (mirror of `ops/n8n/web01-deploy.json`'s pattern) that POSTs to `https://web01.bengtson.local/api/v1/recurring-invoices/run-due` with the operator's service-account bearer token. Run early-morning UTC. The endpoint is idempotent within a day.

## Phase 2 follow-ups

- **Auto-email integration** with #244 — toggle is wired but the actual email send is a no-op until a Phase 2 follow-up turns the `auto_email=true` path into a `send_email` call. WeasyPrint PDF for invoice attachment is needed first.
- **Per-line "use latest price"** toggle. Phase 1 is snapshot-only.
- **Frontend** — no recurring-invoices UI yet; rule management is API-only today.
- **n8n workflow JSON** — `ops/n8n/recurring-invoices-daily.json` deferred until the cron is actually wired up by the operator.
- **Tax / shipping** in the template (currently zero in v1).
