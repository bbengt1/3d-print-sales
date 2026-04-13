from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.models.sale import Sale

SUPPORTED_SHIPPING_LABEL_FORMAT = "html-4x6-v1"
SUPPORTED_SHIPPING_LABEL_SIZE = "4x6"


class ShippingLabelValidationError(ValueError):
    """Raised when a sale is missing required shipping-label data."""


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def get_shipping_label_missing_fields(sale: Sale) -> list[str]:
    missing: list[str] = []
    if not _clean(sale.shipping_recipient_name) and not _clean(sale.customer_name):
        missing.append("recipient name")
    if not _clean(sale.shipping_address_line1):
        missing.append("address line 1")
    if not _clean(sale.shipping_city):
        missing.append("city")
    if not _clean(sale.shipping_state):
        missing.append("state")
    if not _clean(sale.shipping_postal_code):
        missing.append("postal code")
    if not _clean(sale.shipping_country):
        missing.append("country")
    return missing


def shipping_label_ready(sale: Sale) -> bool:
    return not get_shipping_label_missing_fields(sale)


def assert_shipping_label_ready(sale: Sale) -> None:
    missing = get_shipping_label_missing_fields(sale)
    if not missing:
        return
    detail = ", ".join(missing)
    raise ShippingLabelValidationError(
        f"Shipping label requires the following fields before printing: {detail}"
    )


def mark_shipping_label_generated(sale: Sale) -> None:
    if sale.shipping_label_generated_at is None:
        sale.shipping_label_generated_at = datetime.now(timezone.utc)


def mark_shipping_label_printed(sale: Sale) -> None:
    now = datetime.now(timezone.utc)
    if sale.shipping_label_generated_at is None:
        sale.shipping_label_generated_at = now
    sale.shipping_label_last_printed_at = now
    sale.shipping_label_print_count = (sale.shipping_label_print_count or 0) + 1


def render_sale_shipping_label_html(sale: Sale) -> str:
    assert_shipping_label_ready(sale)

    recipient = _clean(sale.shipping_recipient_name) or _clean(sale.customer_name) or "Recipient"
    company = _clean(sale.shipping_company)
    address_line_1 = _clean(sale.shipping_address_line1) or ""
    address_line_2 = _clean(sale.shipping_address_line2)
    city = _clean(sale.shipping_city) or ""
    state = _clean(sale.shipping_state) or ""
    postal_code = _clean(sale.shipping_postal_code) or ""
    country = _clean(sale.shipping_country) or ""
    tracking = _clean(sale.tracking_number)

    item_lines = "".join(
        f"<li>{escape(item.description)} x {item.quantity}</li>"
        for item in sale.items[:8]
    )
    if len(sale.items) > 8:
        item_lines += f"<li>+ {len(sale.items) - 8} more item(s)</li>"

    tracking_markup = (
        f"""
        <section class="tracking">
          <div class="section-label">Tracking</div>
          <div class="tracking-code">{escape(tracking)}</div>
        </section>
        """
        if tracking
        else """
        <section class="tracking tracking-empty">
          <div class="section-label">Tracking</div>
          <div class="tracking-code">Add tracking number in the sale record before carrier handoff.</div>
        </section>
        """
    )

    company_markup = f'<div class="address-line company">{escape(company)}</div>' if company else ""
    address_line_2_markup = (
        f'<div class="address-line">{escape(address_line_2)}</div>' if address_line_2 else ""
    )
    notes_markup = (
        f"""
        <section class="notes">
          <div class="section-label">Notes</div>
          <div class="notes-copy">{escape(sale.notes)}</div>
        </section>
        """
        if _clean(sale.notes)
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{escape(sale.sale_number)} Shipping Label</title>
    <style>
      @page {{
        size: 4in 6in;
        margin: 0;
      }}

      * {{
        box-sizing: border-box;
      }}

      html,
      body {{
        margin: 0;
        padding: 0;
        width: 4in;
        height: 6in;
        background: #fff;
        color: #111827;
        font-family: Arial, Helvetica, sans-serif;
      }}

      body {{
        padding: 0.18in;
      }}

      .label {{
        display: flex;
        flex-direction: column;
        gap: 0.14in;
        width: 100%;
        height: 100%;
      }}

      .topbar {{
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        border-bottom: 2px solid #111827;
        padding-bottom: 0.08in;
      }}

      .brand {{
        font-size: 0.24in;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}

      .sale-number {{
        font-size: 0.17in;
        font-weight: 700;
      }}

      .section-label {{
        font-size: 0.12in;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #4b5563;
        margin-bottom: 0.04in;
      }}

      .ship-to {{
        border: 2px solid #111827;
        padding: 0.12in;
        min-height: 1.65in;
      }}

      .recipient {{
        font-size: 0.26in;
        font-weight: 700;
        margin-bottom: 0.04in;
      }}

      .company,
      .address-line,
      .city-line {{
        font-size: 0.2in;
        line-height: 1.2;
      }}

      .tracking {{
        border: 2px solid #111827;
        padding: 0.12in;
      }}

      .tracking-code {{
        font-size: 0.28in;
        font-weight: 700;
        letter-spacing: 0.02em;
        word-break: break-word;
      }}

      .tracking-empty .tracking-code {{
        font-size: 0.16in;
        font-weight: 500;
      }}

      .meta {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.12in;
      }}

      .meta-card,
      .items,
      .notes {{
        border: 1px solid #d1d5db;
        padding: 0.1in;
      }}

      .meta-copy {{
        font-size: 0.16in;
        line-height: 1.3;
      }}

      .items-list {{
        margin: 0;
        padding-left: 0.2in;
        font-size: 0.15in;
        line-height: 1.25;
      }}

      .notes-copy {{
        font-size: 0.14in;
        line-height: 1.25;
        white-space: pre-wrap;
      }}

      .footer {{
        margin-top: auto;
        font-size: 0.13in;
        color: #4b5563;
        border-top: 1px solid #d1d5db;
        padding-top: 0.08in;
      }}
    </style>
  </head>
  <body>
    <main class="label">
      <header class="topbar">
        <div class="brand">3D Print Sales</div>
        <div class="sale-number">{escape(sale.sale_number)}</div>
      </header>

      <section class="ship-to">
        <div class="section-label">Ship To</div>
        <div class="recipient">{escape(recipient)}</div>
        {company_markup}
        <div class="address-line">{escape(address_line_1)}</div>
        {address_line_2_markup}
        <div class="city-line">{escape(city)}, {escape(state)} {escape(postal_code)}</div>
        <div class="address-line">{escape(country)}</div>
      </section>

      {tracking_markup}

      <section class="meta">
        <div class="meta-card">
          <div class="section-label">Order Date</div>
          <div class="meta-copy">{sale.date.isoformat()}</div>
        </div>
        <div class="meta-card">
          <div class="section-label">Status</div>
          <div class="meta-copy">{escape(sale.status.title())}</div>
        </div>
      </section>

      <section class="items">
        <div class="section-label">Contents</div>
        <ul class="items-list">{item_lines}</ul>
      </section>

      {notes_markup}

      <footer class="footer">
        Format: {SUPPORTED_SHIPPING_LABEL_FORMAT} | Label size: {SUPPORTED_SHIPPING_LABEL_SIZE} in
      </footer>
    </main>
  </body>
</html>
"""
