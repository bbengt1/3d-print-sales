from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.material import Material
from app.models.product import Product
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel


@pytest_asyncio.fixture
async def seed_report_data(db_session: AsyncSession, seed_material: Material):
    """Create sample jobs, products, sales for report testing."""
    # Create a product
    product = Product(
        name="Widget",
        sku="PRD-PLA-0001",
        material_id=seed_material.id,
        unit_price=Decimal("10.00"),
        unit_cost=Decimal("4.00"),
        stock_qty=20,
    )
    db_session.add(product)
    await db_session.flush()

    # Create a job
    job = Job(
        job_number="J-001",
        date=date(2026, 3, 15),
        product_name="Widget",
        qty_per_plate=4,
        num_plates=2,
        material_id=seed_material.id,
        total_pieces=8,
        material_per_plate_g=Decimal("25"),
        print_time_per_plate_hrs=Decimal("2"),
        labor_mins=Decimal("30"),
        electricity_cost=Decimal("0.50"),
        material_cost=Decimal("5.00"),
        labor_cost=Decimal("12.50"),
        design_cost=Decimal("0"),
        machine_cost=Decimal("3.00"),
        packaging_cost=Decimal("1.25"),
        shipping_cost=Decimal("0"),
        failure_buffer=Decimal("1.11"),
        subtotal_cost=Decimal("23.36"),
        overhead=Decimal("2.45"),
        total_cost=Decimal("25.81"),
        cost_per_piece=Decimal("3.23"),
        price_per_piece=Decimal("5.38"),
        total_revenue=Decimal("43.00"),
        platform_fees=Decimal("4.09"),
        net_profit=Decimal("13.11"),
        profit_per_piece=Decimal("1.64"),
    )
    db_session.add(job)
    await db_session.flush()

    # Create a channel
    channel = SalesChannel(
        name="Etsy",
        platform_fee_pct=Decimal("6.5"),
        fixed_fee=Decimal("0.20"),
    )
    db_session.add(channel)
    await db_session.flush()

    # Create a sale with items
    sale = Sale(
        sale_number="S-2026-0001",
        date=date(2026, 3, 18),
        customer_name="Test Customer",
        channel_id=channel.id,
        payment_method="card",
        status="paid",
        subtotal=Decimal("20.00"),
        shipping_charged=Decimal("5.00"),
        shipping_cost=Decimal("3.50"),
        platform_fees=Decimal("1.50"),
        tax_collected=Decimal("0"),
        total=Decimal("25.00"),
        net_revenue=Decimal("20.00"),
    )
    db_session.add(sale)
    await db_session.flush()

    item = SaleItem(
        sale_id=sale.id,
        product_id=product.id,
        description="Widget",
        quantity=2,
        unit_price=Decimal("10.00"),
        line_total=Decimal("20.00"),
        unit_cost=Decimal("4.00"),
    )
    db_session.add(item)
    await db_session.commit()

    return {"product": product, "job": job, "sale": sale, "channel": channel}


# ── Inventory Report ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inventory_report(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_products"] >= 1
    assert data["total_stock_value"] > 0
    assert len(data["stock_levels"]) >= 1
    assert len(data["material_usage"]) >= 1


@pytest.mark.asyncio
async def test_inventory_report_csv(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/inventory/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "sku" in resp.text
    assert "Widget" in resp.text


@pytest.mark.asyncio
async def test_inventory_turnover(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/inventory")
    data = resp.json()
    assert len(data["turnover"]) >= 1
    widget = next((t for t in data["turnover"] if t["product"] == "Widget"), None)
    assert widget is not None
    assert widget["sold_qty"] >= 2  # 2 items sold


# ── Sales Report ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sales_report(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/sales")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_orders"] >= 1
    assert data["gross_sales"] > 0
    assert data["gross_profit"] >= 0
    assert "platform_fees" in data
    assert "shipping_costs" in data
    assert "contribution_margin" in data
    assert data["net_profit"] is None
    assert len(data["period_data"]) >= 1
    assert len(data["top_products"]) >= 1
    assert len(data["channel_breakdown"]) >= 1
    assert len(data["payment_method_breakdown"]) >= 1


@pytest.mark.asyncio
async def test_sales_report_period(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/sales", params={"period": "daily"})
    assert resp.status_code == 200
    data = resp.json()
    # Daily should show specific dates
    assert any("2026-03-18" in p["period"] for p in data["period_data"])


@pytest.mark.asyncio
async def test_sales_report_csv(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/sales/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "gross_sales" in resp.text
    assert "contribution_margin" in resp.text


@pytest.mark.asyncio
async def test_sales_report_date_filter(client: AsyncClient, seed_report_data):
    # Future date range - should return empty
    resp = await client.get("/api/v1/reports/sales", params={"date_from": "2030-01-01"})
    data = resp.json()
    assert data["total_orders"] == 0


@pytest.mark.asyncio
async def test_sales_report_supports_channel_and_payment_method_filters(client: AsyncClient, seed_report_data):
    channel_id = seed_report_data["channel"].id
    resp = await client.get(
        "/api/v1/reports/sales",
        params={"channel_id": str(channel_id), "payment_method": "card"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_orders"] == 1
    assert data["channel_breakdown"][0]["channel_name"] == "Etsy"
    assert data["payment_method_breakdown"][0]["payment_method"] == "card"


# ── P&L Report ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pl_report(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/pl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["total_revenue"] > 0
    assert data["summary"]["total_costs"] > 0
    assert data["summary"]["gross_profit"] != 0
    assert data["summary"]["reporting_basis"] == "sales_realized_revenue"
    assert len(data["period_data"]) >= 1


@pytest.mark.asyncio
async def test_pl_report_separates_operational_estimate_from_realized_sales(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/pl")
    data = resp.json()
    assert data["summary"]["operational_production_estimate"] > 0
    assert data["summary"]["sales_revenue"] > 0
    assert data["summary"]["total_revenue"] == data["summary"]["sales_revenue"]


@pytest.mark.asyncio
async def test_pl_report_csv(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/pl/csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "operational_production_estimate" in resp.text
    assert "gross_profit" in resp.text


@pytest.mark.asyncio
async def test_pl_report_period_grouping(client: AsyncClient, seed_report_data):
    resp = await client.get("/api/v1/reports/pl", params={"period": "yearly"})
    data = resp.json()
    assert len(data["period_data"]) >= 1
    assert data["period_data"][0]["period"] == "2026"
