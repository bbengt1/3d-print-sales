# Sales Tax Liability and Remittance Workflow

This document describes the initial sales-tax liability foundation added for Phase 16.

## Current Model

The app now supports:
- `tax_profiles`
- `tax_remittances`
- sale-level tax treatment classification

## Tax Profile Fields

Current tax profile records include:
- name
- jurisdiction
- tax rate
- filing frequency
- marketplace-facilitated flag
- active/inactive state
- notes

## Sale Tax Treatment

Each sale can now carry:
- `tax_profile_id`
- `tax_treatment`

Supported treatment values:
- `seller_collected`
- `marketplace_facilitated`
- `non_taxable`

## Liability Logic

Current report behavior distinguishes:
- seller-collected tax → business liability
- marketplace-facilitated tax → informational, not owed by the seller in the same way
- remitted tax → reduces outstanding seller liability

Current outstanding liability formula:
- `seller_collected - remitted`

## Remittance Workflow

Current remittance records include:
- tax profile
- period start/end
- remittance date
- amount
- reference number
- notes

## Current Reporting

The tax liability report currently shows, by profile:
- seller-collected tax
- marketplace-facilitated tax
- remitted tax
- outstanding liability

## Current Limitation

This slice establishes liability-aware tax tracking and remittance records, but it does not yet include more advanced jurisdiction hierarchies, auto-tax calculation, or marketplace settlement reconciliation.

## Related Files

- `backend/app/models/tax_profile.py`
- `backend/app/models/tax_remittance.py`
- `backend/app/api/v1/endpoints/tax.py`
- `backend/tests/test_api_tax.py`
