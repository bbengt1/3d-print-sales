# Quotes Workflow

This document describes the initial quote workflow foundation added for Phase 15.

## Current Model

The app now supports a standalone `quotes` entity for custom work estimates.

Current quote fields include:
- quote number
- quote date
- valid-until date
- customer / customer name
- product name
- print inputs copied from job-style costing
- calculated cost and pricing fields
- notes
- status
- linked converted job (when applicable)

## Supported Statuses

- `draft`
- `sent`
- `accepted`
- `rejected`
- `expired`

## Quote Costing

Quotes reuse the existing job cost calculator so the estimate is based on the same pricing/cost assumptions already used elsewhere in the app.

That means quotes currently calculate:
- total pieces
- electricity/material/labor/design/machine/packaging/shipping cost
- failure buffer
- subtotal and overhead
- total cost
- cost per piece
- target margin based pricing
- total revenue estimate
- platform fees
- net profit
- profit per piece

## Conversion Workflow

Current downstream conversion support:
- accepted quotes can be converted into jobs

Current conversion behavior:
- quote must be `accepted`
- quote can only be converted once
- conversion creates a new `job`
- the quote stores the linked `job_id`
- job pricing/cost fields are copied from the accepted quote to avoid re-entry

## Current Limitation

This slice establishes the quote workflow entry point for Phase 15, but it does not yet include invoice generation, payment tracking, or full quote-line modeling.

## Related Files

- `backend/app/models/quote.py`
- `backend/app/schemas/quote.py`
- `backend/app/api/v1/endpoints/quotes.py`
- `backend/tests/test_api_quotes.py`
