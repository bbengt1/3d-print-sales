# Scrap, Waste, and Failed-Print Workflows

This document describes the current scrap/waste workflow foundation added for inventory accounting.

## Supported Event Types

The app now supports dedicated inventory transaction event types for:
- `scrap`
- `failed_print`
- `writeoff`
- `rework`

## Current Behavior

A scrap/waste event:
- creates an `inventory_transactions` record with a negative quantity
- reduces product stock quantity
- records a reason and optional notes
- uses either the product's current `unit_cost` or an explicitly supplied override cost

## Example Use Cases

### Scrap
Use when finished inventory is damaged or unusable.

### Failed Print
Use when a print run fails before it can be sold as usable finished goods.

### Writeoff
Use when inventory is being intentionally removed from stock for accounting/operational cleanup.

### Rework
Use when inventory is taken out of normal available stock because it requires correction or rework.

## Current Limitation

This foundation records the inventory-side event and stock impact, but it does not yet create a dedicated scrap-expense journal posting. That can be expanded in a later accounting phase if desired.

## Related Files

- `backend/app/services/inventory_service.py`
- `backend/tests/test_inventory_scrap.py`
