from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Iterable

from app.models.plate import Plate
from app.schemas.plate import PlateIn


def build_uniform_plates(
    *,
    qty_per_plate: int,
    num_plates: int,
    material_per_plate_g: Decimal,
    print_time_per_plate_hrs: Decimal,
    printer_id: uuid.UUID | None,
) -> list[Plate]:
    """Expand the legacy uniform inputs into N identical Plate rows."""
    return [
        Plate(
            plate_number=i + 1,
            printer_id=printer_id,
            parts_count=qty_per_plate,
            material_g=material_per_plate_g,
            print_time_hrs=print_time_per_plate_hrs,
        )
        for i in range(num_plates)
    ]


def build_plates_from_input(plates_in: Iterable[PlateIn]) -> list[Plate]:
    """Materialize PlateIn payloads into Plate rows, assigning sequential plate_numbers when omitted."""
    result: list[Plate] = []
    auto = 1
    seen: set[int] = set()
    for entry in plates_in:
        number = entry.plate_number if entry.plate_number is not None else auto
        while number in seen:
            number += 1
        seen.add(number)
        auto = max(auto, number) + 1
        result.append(
            Plate(
                plate_number=number,
                printer_id=entry.printer_id,
                parts_count=entry.parts_count,
                material_g=Decimal(entry.material_g),
                print_time_hrs=Decimal(entry.print_time_hrs),
            )
        )
    return result


def aggregate_plate_totals(plates: Iterable[Plate], *, mixed: bool = False) -> tuple[int, Decimal, Decimal]:
    """Return (total_pieces, total_material_g, total_print_time_hrs) for a plate collection.

    Uniform jobs (`mixed=False`): each plate is an independent duplicate, so
    total_pieces = sum(parts_count). Mixed (multi-part assembly) jobs:
    each plate produces a different part of one finished piece, so
    total_pieces = min(parts_count) — the number of complete assemblies.
    Material and print time always sum (every plate runs).
    """
    plates_list = list(plates)
    if not plates_list:
        return 0, Decimal(0), Decimal(0)
    total_material_g = sum((Decimal(p.material_g) for p in plates_list), Decimal(0))
    total_print_hrs = sum((Decimal(p.print_time_hrs) for p in plates_list), Decimal(0))
    parts = [int(p.parts_count) for p in plates_list]
    total_pieces = min(parts) if mixed else sum(parts)
    return total_pieces, total_material_g, total_print_hrs


def is_uniform(plates: list[Plate]) -> tuple[bool, int | None, int | None, Decimal | None, Decimal | None]:
    """Detect whether a plate set is uniform; return (is_uniform, qty_per_plate, num_plates, material_per_plate_g, print_time_per_plate_hrs)."""
    if not plates:
        return False, None, None, None, None
    first = plates[0]
    for p in plates[1:]:
        if (
            int(p.parts_count) != int(first.parts_count)
            or Decimal(p.material_g) != Decimal(first.material_g)
            or Decimal(p.print_time_hrs) != Decimal(first.print_time_hrs)
        ):
            return False, None, None, None, None
    return (
        True,
        int(first.parts_count),
        len(plates),
        Decimal(first.material_g),
        Decimal(first.print_time_hrs),
    )
