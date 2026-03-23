# A/R Payments, Customer Credits, and Aging

This document describes the accounts receivable tracking foundation added for Phase 15.

## Current Model

The app now supports:
- `payments`
- `customer_credits`
- invoice aging buckets derived from unpaid invoice balances

## Payment Fields

Current payment records include:
- customer
- invoice
- payment date
- amount
- payment method
- reference number
- notes
- unapplied amount

## Customer Credit Fields

Current customer credit records include:
- customer
- invoice
- credit date
- amount
- remaining amount
- reason
- notes

## Payment Allocation Behavior

Current behavior:
- payments can be recorded directly against an invoice
- if payment exceeds invoice balance, the excess is stored as `unapplied_amount`
- invoice `amount_paid` and `balance_due` update from the applied portion

## Credit Behavior

Current behavior:
- customer credits are first-class records
- credits track `remaining_amount`
- credits can be applied to invoices for the same customer
- applying credit reduces both invoice balance and credit remaining balance

## A/R Aging Buckets

Current report buckets:
- `current`
- `1-30`
- `31-60`
- `61-90`
- `90+`

Current report basis:
- unpaid, non-void invoice balances only
- aging is based on due date relative to the requested `as_of_date`

## Current Limitation

This slice adds A/R tracking foundations, but unpaid invoice dashboard widgets and more advanced unapplied-cash/credit allocation workflows can still be expanded later.

## Related Files

- `backend/app/models/payment.py`
- `backend/app/models/customer_credit.py`
- `backend/app/schemas/ar.py`
- `backend/app/api/v1/endpoints/invoices.py`
- `backend/tests/test_api_ar.py`
