# Material Receipts and Valuation

This document explains the raw material receipt / lot costing approach introduced for inventory accounting groundwork.

## Current Valuation Approach

The app now supports recording raw material purchases as **material receipts** tied to a material.

Each receipt stores:
- vendor name
- purchase date
- receipt/reference number
- purchased quantity in grams
- remaining quantity in grams
- direct unit cost per gram
- landed cost total
- landed cost per gram
- total receipt cost
- valuation method marker

## Selected Method

Current implementation supports documenting:
- `lot`
- `average`

Operationally, the current stored receipt model is **lot-aware**, because each purchase is stored separately with its own remaining quantity.

For the material master record’s current `cost_per_g`, the app currently updates that value using an **aggregate weighted average across recorded receipts**.

### Practical interpretation
- receipt records preserve lot-level detail
- material-level current cost basis is updated from receipt data using weighted average logic

This is a reasonable bridge step before deeper Phase 13/14 inventory accounting work.

## Landed Cost Logic

For each receipt:

- `landed_cost_per_g = landed_cost_total / quantity_purchased_g`
- `total_cost = (unit_cost_per_g * quantity_purchased_g) + landed_cost_total`

Example:
- quantity purchased: `1000 g`
- direct unit cost: `0.020000/g`
- landed cost total: `5.00`

Then:
- direct material cost = `20.00`
- landed cost per g = `0.005000`
- total cost = `25.00`

## Current Limitation

The current implementation does **not yet consume/deplete receipts automatically** through production usage or material issue transactions.

That comes later when Phase 13 inventory postings and COGS recognition are implemented.

So for now, receipt records provide:
- real purchase history
- lot-level traceability
- a better material cost basis than manual-only spool settings

## Related Files

- `backend/app/models/material_receipt.py`
- `backend/app/services/material_receipt_service.py`
- `backend/app/api/v1/endpoints/materials.py`
- `backend/tests/test_material_receipts.py`
