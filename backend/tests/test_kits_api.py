from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.product import Product


async def _make_product(db_session, sku: str, name: str) -> Product:
    from app.models.material import Material
    from decimal import Decimal
    from sqlalchemy import select
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
async def test_define_kit(client: AsyncClient, auth_headers, db_session):
    kit = await _make_product(db_session, "KIT-1", "Big Kit")
    a = await _make_product(db_session, "COMP-A", "Component A")
    b = await _make_product(db_session, "COMP-B", "Component B")
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [
            {"component_product_id": str(a.id), "quantity": "2"},
            {"component_product_id": str(b.id), "quantity": "1"},
        ]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["components"]) == 2


@pytest.mark.asyncio
async def test_kit_self_reference_rejected(client: AsyncClient, auth_headers, db_session):
    p = await _make_product(db_session, "KIT-self", "Self-kit")
    await db_session.commit()
    resp = await client.put(
        f"/api/v1/kits/{p.id}",
        json={"components": [{"component_product_id": str(p.id), "quantity": "1"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_kit_unknown_component_rejected(client: AsyncClient, auth_headers, db_session):
    import uuid
    p = await _make_product(db_session, "KIT-X", "kit X")
    await db_session.commit()
    resp = await client.put(
        f"/api/v1/kits/{p.id}",
        json={"components": [{"component_product_id": str(uuid.uuid4()), "quantity": "1"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_kit_replace_components(client: AsyncClient, auth_headers, db_session):
    kit = await _make_product(db_session, "KIT-R", "kit R")
    a = await _make_product(db_session, "RA", "comp A")
    b = await _make_product(db_session, "RB", "comp B")
    c = await _make_product(db_session, "RC", "comp C")
    await db_session.commit()
    await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [{"component_product_id": str(a.id), "quantity": "1"}]},
        headers=auth_headers,
    )
    # Replace
    resp = await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [
            {"component_product_id": str(b.id), "quantity": "2"},
            {"component_product_id": str(c.id), "quantity": "3"},
        ]},
        headers=auth_headers,
    )
    body = resp.json()
    assert len(body["components"]) == 2
    component_ids = {c["component_product_id"] for c in body["components"]}
    assert str(a.id) not in component_ids
    assert str(b.id) in component_ids
    assert str(c.id) in component_ids


@pytest.mark.asyncio
async def test_clear_kit(client: AsyncClient, auth_headers, db_session):
    kit = await _make_product(db_session, "KIT-C", "kit C")
    a = await _make_product(db_session, "CA", "ca")
    await db_session.commit()
    await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [{"component_product_id": str(a.id), "quantity": "1"}]},
        headers=auth_headers,
    )
    resp = await client.delete(f"/api/v1/kits/{kit.id}", headers=auth_headers)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/kits/{kit.id}", headers=auth_headers)
    assert get_resp.json()["components"] == []


@pytest.mark.asyncio
async def test_list_kits_only_includes_kits(client: AsyncClient, auth_headers, db_session):
    kit = await _make_product(db_session, "KIT-L", "kit L")
    not_kit = await _make_product(db_session, "PROD-L", "plain product")
    a = await _make_product(db_session, "LA", "la")
    await db_session.commit()
    await client.put(
        f"/api/v1/kits/{kit.id}",
        json={"components": [{"component_product_id": str(a.id), "quantity": "1"}]},
        headers=auth_headers,
    )
    resp = await client.get("/api/v1/kits", headers=auth_headers)
    ids = resp.json()["kit_product_ids"]
    assert str(kit.id) in ids
    assert str(not_kit.id) not in ids
