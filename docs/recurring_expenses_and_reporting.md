# Recurring Expenses and Expense Reporting

This document describes the recurring expense template and expense reporting foundation added for Phase 14.

## Recurring Expense Templates

The app now supports recurring expense templates that can later generate real bill records.

Current recurring expense fields:
- vendor
- expense category
- mapped account
- description
- amount
- tax amount
- frequency
- next due date
- payment method
- notes
- active/inactive state
- last generated timestamp

## Supported Frequencies

- weekly
- monthly
- quarterly
- yearly

## Current Generation Workflow

A recurring template can generate a bill when:
- it is active
- the requested `as_of_date` is on or after `next_due_date`

Generation result:
- creates a normal `bill`
- advances `next_due_date` based on frequency

## Expense Reporting

Current reporting endpoints summarize bills by:
- expense category
- vendor

Current summary fields:
- key
- label
- total amount
- bill count

## Current Limitation

This phase adds basic recurring generation and grouped reporting, but it does not yet include scheduler/cron automation or more advanced date-bucket analytics.

## Related Files

- `backend/app/models/recurring_expense.py`
- `backend/app/api/v1/endpoints/accounting.py`
- `backend/tests/test_api_recurring_expenses.py`
