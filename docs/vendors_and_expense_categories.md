# Vendors and Expense Categories

This document describes the vendor and expense-category foundation added for Phase 14.

## Vendors

Vendor records store reference data for businesses or suppliers the company buys from.

Current vendor fields:
- name
- contact name
- email
- phone
- notes
- active/inactive state

## Expense Categories

Expense categories group bills/expenses into named buckets and map each category to an accounting account.

Current expense category fields:
- name
- description
- account mapping
- active/inactive state

## Account Mapping Rule

Expense categories currently must map to an account whose type is:
- `expense`, or
- `cogs`

This prevents accidental mapping to invalid account classes like cash or receivables.

## Purpose in Phase 14

These records are reference data for later work in:
- bills and expenses
- due dates / payment tracking
- expense reporting
- recurring expense templates

## Current Limitation

At this stage, vendors and expense categories are foundational master data only. They do not yet create bills, payable balances, or recurring expense instances by themselves.

## Related Files

- `backend/app/models/vendor.py`
- `backend/app/models/expense_category.py`
- `backend/app/api/v1/endpoints/accounting.py`
- `backend/tests/test_api_expenses_admin.py`
