from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

INTERNAL_UPC_PREFIX = "04"
INTERNAL_UPC_NAMESPACE = "internal-upc-a-04"
_SERIAL_DIGITS = 9
_MAX_SERIAL = (10**_SERIAL_DIGITS) - 1


def calculate_upc_a_check_digit(first_eleven_digits: str) -> str:
    """Calculate the UPC-A check digit for an 11-digit numeric payload."""
    if len(first_eleven_digits) != 11 or not first_eleven_digits.isdigit():
        raise ValueError("UPC-A check digit input must be exactly 11 digits.")

    digits = [int(digit) for digit in first_eleven_digits]
    odd_sum = sum(digits[0::2])
    even_sum = sum(digits[1::2])
    check_digit = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10
    return str(check_digit)


def is_valid_upc_a(value: str) -> bool:
    return (
        len(value) == 12
        and value.isdigit()
        and calculate_upc_a_check_digit(value[:11]) == value[-1]
    )


def build_internal_upc_a(serial: int) -> str:
    if serial < 1 or serial > _MAX_SERIAL:
        raise ValueError("Internal UPC serial is outside the supported range.")

    first_eleven = f"{INTERNAL_UPC_PREFIX}{serial:0{_SERIAL_DIGITS}d}"
    return first_eleven + calculate_upc_a_check_digit(first_eleven)


def _serial_from_internal_upc(value: str | None) -> int | None:
    if (
        not value
        or len(value) != 12
        or not value.startswith(INTERNAL_UPC_PREFIX)
        or not value.isdigit()
    ):
        return None
    if not is_valid_upc_a(value):
        return None
    return int(value[len(INTERNAL_UPC_PREFIX):11])


async def generate_unique_internal_upc_a(db: AsyncSession) -> str:
    """Generate the next unused internal UPC-A value, reserving archived products too."""
    result = await db.execute(
        select(Product.upc).where(Product.upc.like(f"{INTERNAL_UPC_PREFIX}%"))
    )
    existing_values = {upc for upc in result.scalars().all() if upc}
    max_serial = max(
        (
            serial
            for serial in (_serial_from_internal_upc(upc) for upc in existing_values)
            if serial is not None
        ),
        default=0,
    )

    for serial in range(max_serial + 1, _MAX_SERIAL + 1):
        candidate = build_internal_upc_a(serial)
        if candidate not in existing_values:
            return candidate

    raise RuntimeError("No internal UPC-A values remain in the configured namespace.")
