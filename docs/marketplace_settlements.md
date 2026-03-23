# Marketplace Settlements and Payout Reconciliation

This document describes the initial marketplace settlement foundation added for Phase 16.

## Current Model

The app now supports:
- `marketplace_settlements`
- `settlement_lines`

A settlement can be linked to:
- a sales channel
- underlying sales on individual settlement lines

## Settlement Fields

Current settlement records include:
- settlement number
- sales channel
- period start/end
- payout date
- gross sales
- marketplace fees
- adjustments
- reserves held
- net deposit
- expected net
- discrepancy amount
- notes

## Settlement Line Fields

Current settlement lines include:
- linked sale
- line type
- description
- amount
- notes

Supported line types:
- `sale`
- `fee`
- `adjustment`
- `reserve`
- `other`

## Reconciliation Logic

Current expected-net logic prefers explicit settlement lines when they are supplied.

That means:
- sale lines contribute to gross sales
- fee lines contribute to marketplace fees
- adjustments and reserves are applied at the settlement header level

Current formula:
- `expected_net = gross_sales - marketplace_fees + adjustments - reserves_held`
- `discrepancy_amount = net_deposit - expected_net`

## Current Reporting

The settlement reconciliation report currently shows:
- gross sales
- marketplace fees
- adjustments
- reserves held
- net deposit
- expected net
- discrepancy amount

## Current Limitation

This slice establishes payout batch recording and reconciliation, but it does not yet include CSV import workflows or richer payout-in-transit dashboard widgets.

## Related Files

- `backend/app/models/marketplace_settlement.py`
- `backend/app/models/settlement_line.py`
- `backend/app/api/v1/endpoints/settlements.py`
- `backend/tests/test_api_settlements.py`
