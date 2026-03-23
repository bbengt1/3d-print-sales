# Invoice Lifecycle

This document describes the initial invoice lifecycle foundation added for Phase 15.

## Current Model

The app now supports:
- `invoices`
- `invoice_lines`

An invoice can be linked to:
- a customer
- an accepted quote

## Invoice Fields

Current invoice records include:
- invoice number
- linked quote
- customer / customer name
- issue date
- due date
- subtotal
- tax amount
- shipping amount
- credits applied
- total due
- amount paid
- balance due
- status
- notes

## Invoice Line Fields

Current invoice line records include:
- description
- quantity
- unit price
- line total
- notes

## Supported Statuses

- `draft`
- `sent`
- `partially_paid`
- `paid`
- `overdue`
- `void`

## Balance Logic

Current derived behavior:
- `subtotal` = sum of invoice line totals
- `total_due` = subtotal + tax + shipping - credits
- `balance_due` = total_due - amount_paid

Status behavior:
- `balance_due <= 0` -> `paid`
- `amount_paid > 0` with remaining balance -> `partially_paid`
- unpaid and past due date -> `overdue`
- explicitly voided invoice remains `void`

## Current Workflow Support

The app currently supports:
- direct invoice creation with line items
- invoice creation from an accepted quote
- payment application against an invoice
- credit application against an invoice
- overdue detection based on due date and unpaid balance
- blocking payment/credit application on void invoices

## Current Limitation

This slice establishes invoice balances and lifecycle handling, but it does not yet include standalone payment records, customer credit ledgers, or full A/R aging reporting.

## Related Files

- `backend/app/models/invoice.py`
- `backend/app/models/invoice_line.py`
- `backend/app/schemas/invoice.py`
- `backend/app/api/v1/endpoints/invoices.py`
- `backend/tests/test_api_invoices.py`
