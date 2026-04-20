"""Barcode and QR code rendering for product labels.

Wraps `python-barcode` (Code128 / UPC-A) and `qrcode` so the product
endpoint can return a ready-to-print PNG. Kept behind a thin service so
tests can stub or swap the libraries later (e.g. switch to SVG output,
server-side caching, thermal-printer-specific DPI tweaks).

Formats:
- ``code128`` — works with any alphanumeric SKU; default for products
  without a UPC.
- ``upc`` — UPC-A; requires a 12-digit numeric input. Raises
  ``ValueError`` when the product's UPC is empty or the wrong length.
- ``qr`` — square QR code; caller decides whether to encode the UPC,
  SKU, or a full product URL.
"""
from __future__ import annotations

from io import BytesIO
from typing import Literal

import barcode
import qrcode
from barcode.writer import ImageWriter

BarcodeFormat = Literal["code128", "upc", "qr"]

# UPC-A is exactly 12 numeric digits. python-barcode raises if the
# length or charset is wrong, but we preflight for a cleaner 400.
_UPC_LENGTH = 12


def render_barcode(
    *,
    format: BarcodeFormat,
    payload: str,
    size: int = 2,
) -> bytes:
    """Render a barcode or QR code to PNG bytes.

    :param format: ``code128`` | ``upc`` | ``qr``.
    :param payload: String content to encode (SKU, UPC, or URL).
    :param size: Visual size hint. For 1D barcodes this is the module
        width in pixels (writer ``module_width``). For QR this is the
        ``box_size`` in pixels.
    :raises ValueError: If ``payload`` is empty, or the format-specific
        validation fails (e.g. UPC must be 12 digits).
    """
    if not payload:
        raise ValueError("Barcode payload is empty")

    size = max(1, min(int(size), 20))

    if format == "qr":
        return _render_qr(payload, box_size=size * 4)

    if format == "upc":
        if len(payload) != _UPC_LENGTH or not payload.isdigit():
            raise ValueError("UPC-A payload must be exactly 12 numeric digits")
        return _render_1d("upca", payload[:-1], module_width=size)

    if format == "code128":
        return _render_1d("code128", payload, module_width=size)

    raise ValueError(f"Unknown barcode format: {format!r}")


def _render_1d(symbology: str, data: str, *, module_width: int) -> bytes:
    writer = ImageWriter()
    # module_width is in mm for python-barcode; scale up so 1 ≈ 0.2mm
    # produces a sharp ~2px bar on screen. Size 2 → 0.4mm ≈ 4px.
    options = {
        "module_width": max(0.2, module_width * 0.2),
        "module_height": 15.0,
        "font_size": 10,
        "text_distance": 4.0,
        "quiet_zone": 4.0,
        "write_text": True,
    }
    barcode_cls = barcode.get_barcode_class(symbology)
    instance = barcode_cls(data, writer=writer)
    buf = BytesIO()
    instance.write(buf, options=options)
    return buf.getvalue()


def _render_qr(data: str, *, box_size: int) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
