from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.kit_component import KitComponent
from app.models.material import Material
from app.models.product import Product


async def _make_product(db_session, sku: str, name: str) -> Product:
    mat = (await db_session.execute(select(Material))).scalars().first()
    if mat is None:
        mat = Material(
            name="Test Material",
            brand="TestBrand",
            spool_weight_g=Decimal("1000"),
            spool_price=Decimal("20"),
            net_usable_g=Decimal("950"),
            cost_per_g=Decimal("20") / Decimal("950"),
        )
        db_session.add(mat)
        await db_session.flush()
    p = Product(sku=sku, name=name, material_id=mat.id)
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_put_kit_rejects_duplicate_component_ids(
    client: AsyncClient, auth_headers, db_session
):
    """P1 #288: PUT with duplicate component_product_id must 400 up front,
    not surface as a 500 from the unique constraint on flush."""
    kit = await _make_product(db_session, "KIT-DUP", "Dup Kit")
    a = await _make_product(db_session, "DUP-A", "Component A")
    b = await _make_product(db_session, "DUP-B", "Component B")
    await db_session.commit()

    # First, set up an existing valid kit definition so we can verify it is
    # not destructively replaced by a bad request.
    setup = await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [
            {"component_product_id": str(a.id), "quantity": "2"},
            {"component_product_id": str(b.id), "quantity": "1"},
        ]},
        headers=auth_headers,
    )
    assert setup.status_code == 200
    original = {
        c["component_product_id"]: Decimal(c["quantity"])
        for c in setup.json()["components"]
    }
    assert len(original) == 2

    # Now PUT with duplicate component_product_id values; should 400.
    resp = await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [
            {"component_product_id": str(a.id), "quantity": "1"},
            {"component_product_id": str(a.id), "quantity": "5"},
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "duplicate" in detail.lower() or str(a.id) in detail

    # Existing components must NOT have been touched (no destructive reset).
    get_resp = await client.get(f"/api/v1/kits/{kit.id}", headers=auth_headers)
    assert get_resp.status_code == 200
    after = {
        c["component_product_id"]: Decimal(c["quantity"])
        for c in get_resp.json()["components"]
    }
    assert after == original

    # And the DB rows should reflect the original definition.
    rows = (
        await db_session.execute(
            select(KitComponent).where(KitComponent.kit_product_id == kit.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    db_ids = {str(r.component_product_id) for r in rows}
    assert db_ids == {str(a.id), str(b.id)}


@pytest.mark.asyncio
async def test_put_kit_rejects_duplicates_on_first_definition(
    client: AsyncClient, auth_headers, db_session
):
    """Even with no prior kit definition, duplicates must 400, and no rows
    must be inserted."""
    kit = await _make_product(db_session, "KIT-DUP2", "Dup Kit 2")
    a = await _make_product(db_session, "DUP2-A", "Component A2")
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [
            {"component_product_id": str(a.id), "quantity": "1"},
            {"component_product_id": str(a.id), "quantity": "2"},
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 400

    rows = (
        await db_session.execute(
            select(KitComponent).where(KitComponent.kit_product_id == kit.id)
        )
    ).scalars().all()
    assert rows == []
