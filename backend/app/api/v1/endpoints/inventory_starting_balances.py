"""#262 P2: Inventory starting-balances CSV import.

CSV row format:
  item_kind,item_identifier,quantity,unit_cost[,notes]

`item_kind` is one of: material | product | supply
`item_identifier` is the model's natural key:
  - material: name (since materials have no SKU column)
  - product:  sku
  - supply:   name (or sku)

Activity guard: refuses to import for an item that already has any
inventory activity (material receipts / inventory transactions / sale
items) unless `?force=true`.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date as _date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.inventory_transaction import InventoryTransaction
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.product import Product
from app.models.sale_item import SaleItem
from app.models.supply import Supply


router = APIRouter(prefix="/inventory/starting-balances", tags=["Inventory"])


REQUIRED_COLUMNS = {"item_kind", "item_identifier", "quantity", "unit_cost"}


async def _has_material_activity(db, material_id: uuid.UUID) -> bool:
    return (
        await db.execute(
            select(MaterialReceipt.id).where(MaterialReceipt.material_id == material_id).limit(1)
        )
    ).first() is not None


async def _has_product_activity(db, product_id: uuid.UUID) -> bool:
    has_tx = (
        await db.execute(
            select(InventoryTransaction.id)
            .where(InventoryTransaction.product_id == product_id)
            .limit(1)
        )
    ).first()
    if has_tx:
        return True
    has_sale = (
        await db.execute(
            select(SaleItem.id).where(SaleItem.product_id == product_id).limit(1)
        )
    ).first()
    return has_sale is not None


@router.post(
    "/inventory.csv",
    summary="#262 P2: Import inventory starting balances from CSV",
)
async def import_inventory_starting_balances(
    user: CurrentUser,
    db: DB,
    file: UploadFile = File(...),
    as_of: _date | None = Query(None, description="Posting date (defaults to today)"),
    force: bool = Query(False, description="Override activity guard"),
):
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must include columns: {sorted(REQUIRED_COLUMNS)}",
        )
    target_date = as_of or _date.today()
    rows = list(reader)
    out: list[dict] = []
    imported = 0

    for idx, r in enumerate(rows, start=2):
        kind = (r.get("item_kind") or "").strip().lower()
        ident = (r.get("item_identifier") or "").strip()
        try:
            qty = Decimal((r.get("quantity") or "0").strip() or "0")
            unit_cost = Decimal((r.get("unit_cost") or "0").strip() or "0")
        except Exception:
            out.append({"row": idx, "error": "invalid quantity or unit_cost"})
            continue
        notes = (r.get("notes") or "").strip() or "Opening balance"

        try:
            if kind == "material":
                m = (
                    await db.execute(select(Material).where(Material.name == ident))
                ).scalar_one_or_none()
                if m is None:
                    out.append({"row": idx, "error": f"material not found: {ident}"})
                    continue
                if not force and await _has_material_activity(db, m.id):
                    out.append({"row": idx, "error": "material has prior activity (pass ?force=true)"})
                    continue
                # quantity is grams
                receipt = MaterialReceipt(
                    material_id=m.id,
                    vendor_name="Opening Balance",
                    purchase_date=target_date,
                    receipt_number=None,
                    quantity_purchased_g=qty,
                    quantity_remaining_g=qty,
                    unit_cost_per_g=unit_cost,
                    landed_cost_total=Decimal("0"),
                    landed_cost_per_g=Decimal("0"),
                    total_cost=(qty * unit_cost).quantize(Decimal("0.01")),
                    valuation_method="lot",
                    notes=notes,
                )
                db.add(receipt)
                imported += 1
                out.append({"row": idx, "kind": "material", "id": str(m.id)})

            elif kind == "product":
                p = (await db.execute(select(Product).where(Product.sku == ident))).scalar_one_or_none()
                if p is None:
                    out.append({"row": idx, "error": f"product not found by sku: {ident}"})
                    continue
                if not force and await _has_product_activity(db, p.id):
                    out.append({"row": idx, "error": "product has prior activity (pass ?force=true)"})
                    continue
                int_qty = int(qty)
                p.stock_qty = (p.stock_qty or 0) + int_qty
                if unit_cost > 0:
                    p.unit_cost = unit_cost
                db.add(
                    InventoryTransaction(
                        product_id=p.id,
                        type="adjustment",
                        quantity=int_qty,
                        unit_cost=unit_cost,
                        notes=f"{notes} (as of {target_date.isoformat()})",
                    )
                )
                imported += 1
                out.append({"row": idx, "kind": "product", "id": str(p.id)})

            elif kind == "supply":
                s = (
                    await db.execute(
                        select(Supply).where((Supply.name == ident) | (Supply.sku == ident))
                    )
                ).scalar_one_or_none()
                if s is None:
                    out.append({"row": idx, "error": f"supply not found: {ident}"})
                    continue
                # No supply-level activity table beyond the bump itself, so the
                # `force` guard for supplies just checks whether on-hand is
                # already non-zero (a proxy for "previously imported").
                if not force and Decimal(s.quantity_on_hand or 0) != 0:
                    out.append({"row": idx, "error": "supply already has on-hand qty (pass ?force=true)"})
                    continue
                s.quantity_on_hand = qty
                if unit_cost > 0:
                    s.unit_cost = unit_cost
                imported += 1
                out.append({"row": idx, "kind": "supply", "id": str(s.id)})

            else:
                out.append({"row": idx, "error": f"unknown item_kind {kind!r}"})
        except Exception as e:
            out.append({"row": idx, "error": str(e)})

    await db.flush()
    await db.commit()
    return {
        "as_of": target_date.isoformat(),
        "total": len(rows),
        "imported": imported,
        "rows": out,
    }
