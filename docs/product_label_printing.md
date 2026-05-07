# Product Label Printing

Issue: `#234`

## Purpose

Product Studio can print barcode and QR labels from the browser for workstation-local printers. The app renders printable HTML in a popup window; the workstation browser owns the final print dialog and printer selection.

## Supported Entry Points

- Product Studio label sheet: `/product-studio/labels`
- Product list row action: `/product-studio/products`
- Product detail action: `/product-studio/products/{id}`

Supported label content:

- product name
- SKU
- Code128, UPC, or QR barcode image
- optional unit price
- Avery 5160 sheet layout for multi-product sheets

## UPC-A Requirements

UPC-A labels require a saved 12-digit numeric UPC on each product. Product SKUs such as `PRD-PLA-0001` can print as Code128 or QR labels, but they cannot render as UPC-A.

When the label sheet page is set to UPC:

- products without a renderable 12-digit UPC show an inline preview message instead of a broken barcode
- sheet printing is blocked until all selected products have renderable UPCs
- the page offers a `Generate UPCs` action for selected products that need internal UPC-A values

Generated UPCs use the internal-use `04` UPC-A namespace and are saved back to the selected product records. Operators should use the Product Studio editor when they need to replace an existing UPC intentionally.

## Popup Behavior

The label popup opens synchronously from the user click with a `Preparing labels...` state before any barcode API calls run. This keeps browser popup blockers from treating the final print window as a delayed async popup.

Once barcode data URLs are ready, the app replaces the preparation screen with the final print HTML. The print dialog is triggered only after the popup document and barcode images have loaded. If a barcode cannot render, the label cell shows an inline error instead of leaving the popup blank.

Browser security notes:

- Popups must be allowed for the app hostname on label-printing workstations.
- The app intentionally keeps the popup writable long enough to inject print HTML, then clears `window.opener` when the browser allows it.
- The popup should show either the preparation state, printable labels, or an inline error. A blank popup is treated as a bug.

## Validation

Baseline validation:

```bash
cd frontend
npm test
npm run build
```

Manual validation:

- print a single product label from a product row
- print a single product label from product detail
- print a multi-product Avery 5160 sheet from Product Studio labels
- select UPC format for a product without a UPC and confirm the preview explains that a saved 12-digit UPC is required
- generate UPCs for selected products from the label sheet page and confirm UPC-A printing becomes available
- confirm the popup is not blank before the print dialog opens
- confirm popup-blocked behavior produces a visible error toast
