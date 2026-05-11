# Expense Claims

Owner-paid (or contractor-fronted) business expenses that the business reimburses. Originally #251; mileage, approval-workflow integration, and reimburse-as-bill added in #324 Phase 2.

## Lifecycle

`draft → submitted → approved → reimbursed → cancelled`

- **draft**: claim with lines but no GL impact yet.
- **submitted**: operator pushed it for review (no GL change). If the `expense_claims.require_approval_to_approve` setting is enabled, submit also creates a pending `ApprovalRequest`.
- **approved**: posts JE
  - Dr each line's expense account
  - Cr Owner Reimbursable Liability (account `2300`)
- **reimbursed**: depending on the path chosen:
  - **Cash path** (`POST /reimburse`): JE Dr Owner Reimbursable Liability, Cr the chosen cash account.
  - **Bill path** (`POST /reimburse-as-bill`, #324 P2): JE Dr Owner Reimbursable Liability, Cr Accounts Payable (`2000`) **plus** a tracking `Bill` row against the chosen vendor. The bill is then paid through the regular `POST /accounting/bills/{id}/payments` flow.
- **cancelled**: from any non-reimbursed state. If the approve JE was already posted, it's reversed automatically.

## Line types

- `expense` (default): `description`, `expense_account_id`, `amount`.
- `mileage` (#324 P2): `description`, `expense_account_id`, `miles`. Amount = `miles × setting "expense_claims.mileage_rate_per_mile"`; rejects mileage lines if the setting is unset.

## Approval-workflow integration (#324 P2)

When `expense_claims.require_approval_to_approve = "true"`:

- `POST /expense-claims/{id}/submit` creates an `ApprovalRequest` of `action_type = "expense_claim_approval"` and leaves the claim in `submitted` status.
- The direct `POST /expense-claims/{id}/approve` returns `400` — operators must approve through `POST /approvals/{approval_id}/approve`, which calls `approve_claim` and posts the GL entry. This keeps the approval audit trail single-source.
- Reject via `POST /approvals/{approval_id}/reject` just records the decision; the claim stays in `submitted` so the operator can edit and resubmit (or cancel).

Operators can also explicitly route a claim through approvals at any time with `POST /expense-claims/{id}/request-approval`, regardless of the setting.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/expense-claims` | List, optional `?status_filter=...`. |
| `POST` | `/api/v1/expense-claims` | Create (one or more lines). |
| `GET` | `/api/v1/expense-claims/{id}` | Detail. |
| `POST` | `/api/v1/expense-claims/{id}/submit` | Draft → submitted (creates an `ApprovalRequest` when the approval-required setting is on). |
| `POST` | `/api/v1/expense-claims/{id}/request-approval` | Explicitly route through the approvals queue. |
| `POST` | `/api/v1/expense-claims/{id}/approve` | Submitted (or draft) → approved + JE. Refuses when approval-required setting is on. |
| `POST` | `/api/v1/expense-claims/{id}/reimburse` | Approved → reimbursed via direct cash JE. Body: `{cash_account_id, paid_on?}`. |
| `POST` | `/api/v1/expense-claims/{id}/reimburse-as-bill` | Approved → reimbursed via vendor bill. Body: `{vendor_id, due_date?, description?}`. |
| `POST` | `/api/v1/expense-claims/{id}/cancel` | Any non-reimbursed state → cancelled. |

`claim_number` allocator scope `expense_claim` with format `EC-{year}-{value:04d}` via #243.

## COA seed

Migration `20260509_09` adds account `2300` "Owner Reimbursable Liability". The reimburse-as-bill path also requires `2000` Accounts Payable (already in the starter COA).

## Settings

| Key | Effect |
|---|---|
| `expense_claims.mileage_rate_per_mile` | Per-mile rate applied to `line_kind = "mileage"` lines at create time. Required for mileage lines. |
| `expense_claims.require_approval_to_approve` | When truthy (`true` / `1` / `yes`), `submit` creates an `ApprovalRequest` instead of the operator approving directly. |

## Phase 2 follow-ups (still deferred)

- **Receipt attachments** per claim line — depends on the frontend, but the existing `AttachmentsPanel` with `scope=expense_claim` already supports document-level attachments today.
- **Frontend**: no expense-claims UI today (admin-API only).
- **Multi-payer** claims, recurring claims.
- **Multi-step approver chains** — the current integration is single-approver via the central `/approvals` queue.
