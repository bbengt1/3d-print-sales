from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.material import Material
from app.models.product import Product
from app.services.product_barcode_service import calculate_upc_a_check_digit


@pytest.mark.asyncio
async def test_create_product(client: AsyncClient, auth_headers: dict, seed_material: Material):
    resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={
            "name": "Phone Stand",
            "description": "Minimalist phone stand",
            "material_id": str(seed_material.id),
            "unit_price": 8.99,
            "reorder_point": 5,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Phone Stand"
    assert data["sku"].startswith("PRD-PLA-")
    assert data["stock_qty"] == 0
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_product_requires_auth(client: AsyncClient, seed_material: Material):
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Test", "material_id": str(seed_material.id)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_products(client: AsyncClient, auth_headers: dict, seed_material: Material):
    # Create two products
    for name in ["Widget A", "Widget B"]:
        await client.post(
            "/api/v1/products",
            headers=auth_headers,
            json={"name": name, "material_id": str(seed_material.id)},
        )
    resp = await client.get("/api/v1/products")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_products_search(client: AsyncClient, auth_headers: dict, seed_material: Material):
    await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Unique Gadget", "material_id": str(seed_material.id)},
    )
    await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Other Thing", "material_id": str(seed_material.id)},
    )
    resp = await client.get("/api/v1/products", params={"search": "Gadget"})
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_products_search_matches_upc(client: AsyncClient, auth_headers: dict, seed_material: Material):
    await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Scannable Widget", "material_id": str(seed_material.id), "upc": "012345678901"},
    )
    resp = await client.get("/api/v1/products", params={"search": "012345678901"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_get_product(client: AsyncClient, auth_headers: dict, seed_material: Material):
    create_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Test Product", "material_id": str(seed_material.id)},
    )
    product_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/products/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Product"


@pytest.mark.asyncio
async def test_get_product_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_product_bom_tracks_material_and_product_components(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    seed_material: Material,
):
    seed_material.spools_in_stock = 2
    await db_session.commit()

    component = Product(
        sku="PRD-PLA-PART",
        name="Printed hinge",
        material_id=seed_material.id,
        unit_cost=3,
        unit_price=6,
        stock_qty=7,
    )
    db_session.add(component)
    await db_session.commit()
    await db_session.refresh(component)

    create_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Desk organizer", "material_id": str(seed_material.id), "unit_price": 18},
    )
    assert create_resp.status_code == 201, create_resp.text
    product_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/products/{product_id}/bom",
        headers=auth_headers,
        json={
            "items": [
                {
                    "component_type": "material",
                    "material_id": str(seed_material.id),
                    "quantity": 100,
                    "unit": "g",
                    "waste_factor_pct": 10,
                    "notes": "body and inserts",
                },
                {
                    "component_type": "product",
                    "component_product_id": str(component.id),
                    "quantity": 2,
                    "unit": "each",
                },
            ]
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["has_bom"] is True
    assert data["buildable_quantity"] == 3
    assert data["blockers"] == []
    assert len(data["items"]) == 2
    assert data["items"][0]["component_name"] == "PLA (Generic)"
    assert float(data["items"][0]["estimated_unit_cost"]) == pytest.approx(2.3158, rel=0.001)
    assert data["items"][1]["component_name"] == "Printed hinge"
    assert data["items"][1]["component_sku"] == "PRD-PLA-PART"
    assert float(data["estimated_unit_cost"]) == pytest.approx(8.3158, rel=0.001)

    product_check = await client.get(f"/api/v1/products/{product_id}")
    assert product_check.json()["stock_qty"] == 0
    assert float(product_check.json()["unit_cost"]) == 0

    summary = await client.get(f"/api/v1/products/{product_id}/bom")
    assert summary.status_code == 200
    assert summary.json()["buildable_quantity"] == 3


@pytest.mark.asyncio
async def test_product_bom_reports_blockers(client: AsyncClient, auth_headers: dict, seed_material: Material):
    create_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Large planter", "material_id": str(seed_material.id)},
    )
    product_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/products/{product_id}/bom",
        headers=auth_headers,
        json={
            "items": [
                {
                    "component_type": "material",
                    "material_id": str(seed_material.id),
                    "quantity": 25,
                    "unit": "g",
                }
            ]
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["buildable_quantity"] == 0
    assert data["items"][0]["is_blocked"] is True
    assert data["items"][0]["blocker"] == "Insufficient material stock."
    assert "PLA (Generic): Insufficient material stock." in data["blockers"]


@pytest.mark.asyncio
async def test_product_bom_rejects_duplicate_and_circular_components(
    client: AsyncClient,
    auth_headers: dict,
    seed_material: Material,
):
    first = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Assembly A", "material_id": str(seed_material.id)},
    )
    second = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Assembly B", "material_id": str(seed_material.id)},
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    duplicate = await client.put(
        f"/api/v1/products/{first_id}/bom",
        headers=auth_headers,
        json={
            "items": [
                {"component_type": "material", "material_id": str(seed_material.id), "quantity": 5, "unit": "g"},
                {"component_type": "material", "material_id": str(seed_material.id), "quantity": 7, "unit": "g"},
            ]
        },
    )
    assert duplicate.status_code == 400
    assert "Duplicate" in duplicate.json()["detail"]

    seed = await client.put(
        f"/api/v1/products/{first_id}/bom",
        headers=auth_headers,
        json={"items": [{"component_type": "product", "component_product_id": second_id, "quantity": 1}]},
    )
    assert seed.status_code == 200, seed.text

    circular = await client.put(
        f"/api/v1/products/{second_id}/bom",
        headers=auth_headers,
        json={"items": [{"component_type": "product", "component_product_id": first_id, "quantity": 1}]},
    )
    assert circular.status_code == 400
    assert "circular" in circular.json()["detail"]


@pytest.mark.asyncio
async def test_update_product(client: AsyncClient, auth_headers: dict, seed_material: Material):
    create_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Original Name", "material_id": str(seed_material.id)},
    )
    product_id = create_resp.json()["id"]
    resp = await client.put(
        f"/api/v1/products/{product_id}",
        headers=auth_headers,
        json={"name": "Updated Name", "unit_price": 12.50},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert float(resp.json()["unit_price"]) == 12.50


@pytest.mark.asyncio
async def test_create_product_rejects_duplicate_upc(client: AsyncClient, auth_headers: dict, seed_material: Material):
    payload = {"name": "Barcode Product A", "material_id": str(seed_material.id), "upc": "012345678901"}
    first = await client.post("/api/v1/products", headers=auth_headers, json=payload)
    assert first.status_code == 201

    dup = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Barcode Product B", "material_id": str(seed_material.id), "upc": "012345678901"},
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_update_product_rejects_duplicate_upc(client: AsyncClient, auth_headers: dict, seed_material: Material):
    first = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Barcode Product A", "material_id": str(seed_material.id), "upc": "012345678901"},
    )
    second = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Barcode Product B", "material_id": str(seed_material.id), "upc": "999999999999"},
    )
    product_id = second.json()["id"]

    resp = await client.put(
        f"/api/v1/products/{product_id}",
        headers=auth_headers,
        json={"upc": "012345678901"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_generate_product_barcode_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/products/barcode/generate")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_product_barcode_returns_internal_upc_a(client: AsyncClient, auth_headers: dict):
    resp = await client.post("/api/v1/products/barcode/generate", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["format"] == "upc-a"
    assert data["namespace"] == "internal-upc-a-04"
    assert data["upc"].startswith("04")
    assert len(data["upc"]) == 12
    assert data["upc"].isdigit()
    assert calculate_upc_a_check_digit(data["upc"][:11]) == data["upc"][-1]


@pytest.mark.asyncio
async def test_generate_product_barcode_skips_existing_internal_upc(
    client: AsyncClient, auth_headers: dict, seed_material: Material
):
    first = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Existing internal UPC", "material_id": str(seed_material.id), "upc": "040000000013"},
    )
    assert first.status_code == 201, first.text

    resp = await client.post("/api/v1/products/barcode/generate", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["upc"] == "040000000020"


@pytest.mark.asyncio
async def test_delete_product(client: AsyncClient, auth_headers: dict, seed_material: Material):
    create_resp = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "To Delete", "material_id": str(seed_material.id)},
    )
    product_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/products/{product_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify soft-deleted (still exists but inactive)
    get_resp = await client.get(f"/api/v1/products/{product_id}")
    assert get_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_sku_auto_generation(client: AsyncClient, auth_headers: dict, seed_material: Material):
    resp1 = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "First", "material_id": str(seed_material.id)},
    )
    resp2 = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json={"name": "Second", "material_id": str(seed_material.id)},
    )
    assert resp1.json()["sku"] == "PRD-PLA-0001"
    assert resp2.json()["sku"] == "PRD-PLA-0002"


def _make_product_body(name: str, material_id: str, upc: str | None = None) -> dict:
    body: dict = {"name": name, "material_id": material_id}
    if upc is not None:
        body["upc"] = upc
    return body


@pytest.mark.asyncio
async def test_product_barcode_default_code128(
    client: AsyncClient, auth_headers: dict, seed_material: Material
):
    create = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json=_make_product_body("Barcode target", str(seed_material.id)),
    )
    product_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/products/{product_id}/barcode", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert "max-age" in resp.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_product_barcode_qr(
    client: AsyncClient, auth_headers: dict, seed_material: Material
):
    create = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json=_make_product_body("QR target", str(seed_material.id)),
    )
    product_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/products/{product_id}/barcode",
        params={"format": "qr"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_product_barcode_upc_without_upc_returns_400(
    client: AsyncClient, auth_headers: dict, seed_material: Material
):
    create = await client.post(
        "/api/v1/products",
        headers=auth_headers,
        json=_make_product_body("No UPC here", str(seed_material.id)),
    )
    product_id = create.json()["id"]

    resp = await client.get(
        f"/api/v1/products/{product_id}/barcode",
        params={"format": "upc"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "UPC" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_product_barcode_missing_product_returns_404(
    client: AsyncClient, auth_headers: dict
):
    resp = await client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000/barcode",
        headers=auth_headers,
    )
    assert resp.status_code == 404
