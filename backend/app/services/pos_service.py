from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


class POSBarcodeResolutionError(Exception):
    """Raised when a barcode scan cannot be resolved into a sellable product."""


@dataclass
class POSBarcodeResolutionResult:
    product: Product


async def resolve_pos_barcode_scan(
    db: AsyncSession,
    *,
    code: str,
) -> POSBarcodeResolutionResult:
    normalized_code = code.strip()
    if not normalized_code:
        raise POSBarcodeResolutionError("Scan code is required")

    result = await db.execute(select(Product).where(Product.upc == normalized_code))
    matches = result.scalars().all()

    if not matches:
        raise POSBarcodeResolutionError(f"No active product matches barcode '{normalized_code}'")

    active_matches = [product for product in matches if product.is_active]
    if len(active_matches) > 1:
        raise POSBarcodeResolutionError(
            f"Barcode '{normalized_code}' matches multiple active products. Resolve the duplicate UPC before scanning."
        )

    if not active_matches:
        if len(matches) == 1:
            raise POSBarcodeResolutionError(
                f"Barcode '{normalized_code}' belongs to an inactive product. Reactivate it or assign a different barcode."
            )
        raise POSBarcodeResolutionError(
            f"Barcode '{normalized_code}' does not map to a sellable active product."
        )

    product = active_matches[0]
    if product.stock_qty <= 0:
        raise POSBarcodeResolutionError(
            f"{product.name} is out of stock and cannot be added from barcode scan."
        )

    return POSBarcodeResolutionResult(product=product)
