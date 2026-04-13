# Shipping Label Printing

## Purpose

This document defines the first supported remote-compatible thermal shipping-label workflow for issue `#125`.

The design explicitly follows this topology:

`hosted app -> workstation browser -> attached thermal label printer`

The backend does **not** attempt to control USB, serial, or workstation-local printer drivers.

## Supported MVP Path

- Supported label size: `4x6`
- Supported label artifact format: `html-4x6-v1`
- Supported print path: browser-printable HTML opened from the sales workflow and printed by the local workstation
- Supported workflow: create or update shipment fields on a sale, open the print dialog on the workstation, then explicitly mark the label printed after a successful thermal print

This keeps authoritative sale and label data on the hosted app while keeping the printer handoff local to the workstation that actually has the printer attached.

## Backend Contract

The sale record now stores shipment-label fields directly so label content is explicit and printable without depending on mutable customer notes:

- `shipping_recipient_name`
- `shipping_company`
- `shipping_address_line1`
- `shipping_address_line2`
- `shipping_city`
- `shipping_state`
- `shipping_postal_code`
- `shipping_country`
- `shipping_label_generated_at`
- `shipping_label_last_printed_at`
- `shipping_label_print_count`

The sales API now exposes:

- `GET /api/v1/sales/{sale_id}/shipping-label`
  - returns the browser-printable HTML label
  - records `shipping_label_generated_at` the first time a label is generated
  - returns `409` when required shipment fields are missing
- `POST /api/v1/sales/{sale_id}/shipping-label/mark-printed`
  - records operator-confirmed printing
  - increments `shipping_label_print_count`
  - updates `shipping_label_last_printed_at`

## Required Shipment Fields

The label can print only when the sale has:

- recipient name, either `shipping_recipient_name` or fallback `customer_name`
- `shipping_address_line1`
- `shipping_city`
- `shipping_state`
- `shipping_postal_code`
- `shipping_country`

Tracking number is optional for the MVP label format. If it is absent, the printed label shows an operator reminder instead of carrier data.

## Frontend Workflow

The sales UI now supports:

- entering shipment label fields during sale creation
- editing shipment label fields from the sale detail page
- opening the 4x6 print dialog from the sale detail page
- explicit operator confirmation after successful printing
- reprinting by using the same print action again

Behavior rules:

- unsaved shipment edits block printing until saved
- missing shipment fields block printing and are listed in the UI
- canceling the browser print dialog does not mark the label printed
- operators should use `Mark Printed After Successful Print` only after the workstation successfully prints the label
- reprints are allowed and increase `shipping_label_print_count`

## Workstation Assumptions

This MVP assumes:

- the thermal label printer is installed and working on the workstation
- the workstation browser can print a `4x6` page correctly to that printer
- printer-specific scaling, margins, and stock configuration are handled through the workstation browser or printer driver

This MVP does **not** guarantee support for raw printer command languages such as ZPL or EPL.

## Validation

Validated for this implementation:

- `python3.12 -m venv .venv312 && . .venv312/bin/activate && pip install -r backend/requirements.txt websockets && pytest backend/tests/test_api_sales.py -q`
- `cd frontend && npm test`
- `cd frontend && npm run build`

Still required before calling the feature production-ready:

- end-to-end validation with a real thermal printer on a separate workstation against the remotely hosted app
- browser and driver verification for the target printer model
- live deployment validation on `web01` if this is released there
