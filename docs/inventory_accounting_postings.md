# Inventory Accounting Postings

This document describes the current production and sales inventory accounting posting behavior.

## Scope

This is the Phase 13 posting foundation for:
- production completion into finished goods
- sales-time COGS recognition

## Production Completion Posting

When finished goods are added from a completed job, the app posts:
- **Debit** `1400 Finished Goods Inventory`
- **Credit** `1300 Work In Progress Inventory`

### Source
- source type: `job_production`
- source id: job UUID

### Valuation basis
Current value posted:
- `job.cost_per_piece * job.total_pieces`

### Receipt consumption
If the job references a material and material receipts exist, the app currently reduces receipt `quantity_remaining_g` using FIFO by purchase date.

Material used is currently derived as:
- `job.material_per_plate_g * job.num_plates`

## Sales COGS Posting

When product inventory is deducted for a sale, the app posts:
- **Debit** `5000 Material COGS`
- **Credit** `1400 Finished Goods Inventory`

### Source
- source type: `sale_cogs`
- source id: sale UUID

### Valuation basis
Current value posted:
- `sum(sale_item.unit_cost * quantity)` for sale items linked to products

## Duplicate Posting Protection

The app checks for an existing journal entry with the same source type/source id before creating another posting for the same production completion or sale COGS event.

## Current Limitations

- posting currently uses seeded default account codes rather than per-product/per-material account mappings
- COGS debit currently uses `Material COGS` as the seeded default account
- raw-material consumption updates receipt remaining quantity but does not yet create separate raw-material-to-WIP journal entries
- deeper WIP / inventory subledger behavior will likely evolve in later inventory/accounting phases

## Related Files

- `backend/app/services/inventory_accounting_service.py`
- `backend/app/services/inventory_service.py`
- `backend/app/services/sales_service.py`
- `backend/tests/test_inventory_accounting.py`
