# Expense Claims

Owner-paid (or contractor-fronted) business expenses that the business
reimburses. #251.

## Lifecycle

`draft → submitted → approved → reimbursed → cancelled`

- **draft**: claim with lines but no GL impact yet.
- **submitted**: operator pushed it for review (no GL change).
- **approved**: posts JE
  - Dr each line's expense account
  - Cr Owner Reimbursable Liability (account `2300`)
- **reimbursed**: posts JE
  - Dr Owner Reimbursable Liability
  - Cr the chosen cash account
- **cancelled**: from any non-reimbursed state. If the approve JE was already posted, it's reversed automatically.

## API

| Verb | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/expense-claims` | List, optional `?status_filter=...`. |
| `POST` | `/api/v1/expense-claims` | Create (one or more lines). |
| `GET` | `/api/v1/expense-claims/{id}` | Detail. |
| `POST` | `/api/v1/expense-claims/{id}/submit` | Draft → submitted. |
| `POST` | `/api/v1/expense-claims/{id}/approve` | Submitted (or draft) → approved + JE. |
| `POST` | `/api/v1/expense-claims/{id}/reimburse` | Approved → reimbursed + cash JE. |
| `POST` | `/api/v1/expense-claims/{id}/cancel` | Any non-reimbursed state → cancelled. |

`claim_number` allocator scope `expense_claim` with format `EC-{year}-{value:04d}` via #243.

## COA seed

Migration `20260509_09` adds account `2300` "Owner Reimbursable Liability" (idempotent — re-runs against existing installs are safe).

## Phase 2 follow-ups

- **Receipt attachments** via #250 — wire `attachment_service.upload_attachment` calls to expense-claim line forms once the frontend exists.
- **Approval workflow** integration with `approval_request.py` for two-step submit-approve.
- **Reimbursement-as-Bill**: optionally create a real Bill against the payer (treated as a vendor) so the existing AP/payment flow handles cash-out instead of a direct cash-account JE.
- **Frontend**: no expense-claims UI today.
- **Mileage** lines with rate × distance.
- **Multi-payer** claims, recurring claims.
