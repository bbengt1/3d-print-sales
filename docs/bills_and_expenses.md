# Bills and Expenses

This document describes the bill/expense workflow foundation added for Phase 14.

## Current Model

The app now supports:
- `bills`
- `bill_payments`

A bill can be linked to:
- a vendor
- an expense category
- a mapped accounting account

## Bill Fields

Current bill records include:
- vendor
- expense category
- account mapping
- bill number
- description
- issue date
- due date
- amount
- tax amount
- amount paid
- status
- payment method
- notes

## Payment Fields

Current bill payment records include:
- payment date
- amount
- payment method
- reference number
- notes

## Status Logic

Current bill status progression is:
- `open`
- `partially_paid`
- `paid`
- `void`

Derived behavior:
- amount paid = `0` -> `open`
- amount paid > `0` but < amount -> `partially_paid`
- amount paid >= amount -> `paid`
- `void` is preserved when intentionally set

## Validation Rules

- mapped account must be of type `expense` or `cogs`
- payment amount cannot exceed the remaining bill balance
- void bills cannot receive payments

## Current Limitation

This phase establishes the bill/payment operational and payable-tracking model, but it does not yet create a full accounts payable journal workflow or cash disbursement posting.

## Related Files

- `backend/app/models/bill.py`
- `backend/app/models/bill_payment.py`
- `backend/app/api/v1/endpoints/accounting.py`
- `backend/tests/test_api_bills.py`
