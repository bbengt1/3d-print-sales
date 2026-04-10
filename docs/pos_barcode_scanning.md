# POS Barcode Scanning

Issue: `#123`

## Purpose

The POS cashier flow supports remote-compatible barcode scanners that behave like a keyboard and end each scan with `Enter`.

This implementation is intentionally narrow:

- it uses the existing product `upc` field
- it resolves exact UPC matches only
- it supports keyboard-wedge scanners, including scanners connected through remote desktop or browser-based remote sessions
- it adds the scanned product to the POS cart without routing through the general sales form

## Operator Workflow

1. Open the POS page at `/pos`.
2. Scan into the `Barcode Scan` field, or scan while focus is outside other form controls.
3. The app sends the scanned code to `POST /api/v1/pos/scan/resolve`.
4. If one sellable product matches, that product is added to the cart.
5. Complete checkout using the existing POS checkout flow.

## Product Requirements

Each scannable product must have:

- a populated `upc`
- `is_active = true`
- `stock_qty > 0`

The products API now also:

- searches by UPC in the main product list search
- rejects duplicate UPC assignment during create and update with `409 Conflict`

## Error Behavior

Barcode resolution fails when:

- no product matches the scanned code
- the code maps only to an inactive product
- the resolved product is out of stock
- duplicate active products share the same UPC

The POS UI shows the failure inline in the scan panel and leaves the cart unchanged.

## API Surface

- `POST /api/v1/pos/scan/resolve`
  - request: `{ "code": "012345678901" }`
  - response: standard `ProductResponse`
  - `404`: no active product matches the code
  - `409`: duplicate, inactive, or out-of-stock conflict

## Validation

Backend:

```bash
source .venv/bin/activate
python -m pytest backend/tests/test_api_products.py backend/tests/test_api_pos.py -q
```

Frontend:

```bash
cd frontend
npm test
npm run build
```
