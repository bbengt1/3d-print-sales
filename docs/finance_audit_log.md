# Finance Audit Log

This document describes the initial audit-log foundation added for Phase 18.

## Current Model

The app now supports a first-class `audit_logs` table for finance-sensitive actions.

Current audit log fields include:
- actor user
- entity type
- entity id
- action
- optional reason
- before snapshot
- after snapshot
- created timestamp

## Current Coverage

The current implementation records audit entries for:
- manual inventory adjustments
- settings updates
- settings bulk updates
- sale create/update/refund events

It also includes an admin-only audit query endpoint for filtered history lookup.

## Query Surface

Current endpoint:
- `GET /api/v1/audit/logs`

Current filters:
- `entity_type`
- `entity_id`
- `action`
- `limit`

## Current Limitation

This slice establishes the audit-log foundation and covers several of the highest-risk finance-sensitive writes, but broader write-path coverage and approval-specific audit metadata will expand further in the remaining Phase 18 work.

## Related Files

- `backend/app/models/audit_log.py`
- `backend/app/schemas/audit.py`
- `backend/app/services/audit_service.py`
- `backend/app/api/v1/endpoints/audit.py`
- `backend/tests/test_api_audit.py`
