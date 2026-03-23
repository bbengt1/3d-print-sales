# Refund and Manual Adjustment Approvals

This document describes the approval workflow foundation added for Phase 18.

## Current Model

The app now supports first-class `approval_requests` for high-risk finance-sensitive actions.

Current approval request fields include:
- action type
- entity type / entity id
- requested by
- approved by
- status
- reason
- request payload
- decision notes
- created / decided timestamps

## Current Covered Actions

The approval workflow currently covers:
- non-admin manual inventory adjustments
- non-admin sale refunds

## Reason Requirements

Current required documented reasons:
- manual inventory adjustments require a reason
- refunds require a reason

## Current Approval Flow

For covered actions:
- non-admin user submits the action
- system creates a pending `approval_request`
- admin can review via `/api/v1/approvals`
- admin can approve or reject the request
- on approval, the action is executed and audited

## Admin Behavior

Admins can still execute the high-risk action directly, but the reason is still required and the executed action is audit logged.

## Related Files

- `backend/app/models/approval_request.py`
- `backend/app/schemas/approval.py`
- `backend/app/api/v1/endpoints/approvals.py`
- `backend/tests/test_api_approvals.py`
