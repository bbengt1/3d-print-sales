"""#329 P2: tax remittance breakdown by component + reverse-charge tracking."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.customer import Customer
from app.models.sale import Sale
from app.models.sales_channel import SalesChannel
from app.models.tax_profile import TaxProfile, TaxProfileComponent


@pytest.mark.asyncio
async def test_component_breakdown_compound_profile(client: AsyncClient, auth_headers, db_session):
    profile = TaxProfile(name="QC GST+QST", jurisdiction="QC", tax_rate=Decimal("0"), is_compound=True)
    db_session.add(profile)
    await db_session.flush()
    db_session.add(TaxProfileComponent(profile_id=profile.id, name="GST", rate=Decimal("5.000"), apply_order=0))
    db_session.add(TaxProfileComponent(profile_id=profile.id, name="QST", rate=Decimal("9.975"), apply_order=1))
    channel = SalesChannel(name="QC channel")
    db_session.add(channel)
    customer = Customer(name="Test", email="t@t.t")
    db_session.add(customer)
    await db_session.flush()
    sale = Sale(
        date=datetime.date(2026, 4, 1),
        customer_id=customer.id,
        channel_id=channel.id,
        tax_profile_id=profile.id,
        subtotal=Decimal("1000"),
        tax_collected=Decimal("0"),
        shipping_cost=Decimal("0"),
        platform_fees=Decimal("0"),
        total=Decimal("1000"),
        net_revenue=Decimal("1000"),
        sale_number="SAL-1",
        status="completed",
    )
    db_session.add(sale)
    await db_session.commit()

    r = await client.get(
        "/api/v1/tax/reports/component-breakdown",
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    rows = [row for row in body["rows"] if row["profile_name"] == "QC GST+QST"]
    assert len(rows) == 2
    by_name = {row["component_name"]: row for row in rows}
    # GST 5% on 1000 = 50; QST 9.975% on 1050 = 104.74
    assert Decimal(by_name["GST"]["estimated_tax"]) == Decimal("50.00")
    assert Decimal(by_name["QST"]["estimated_tax"]) == Decimal("104.74")


@pytest.mark.asyncio
async def test_liability_marks_reverse_charge_separately(client: AsyncClient, auth_headers, db_session):
    rc = TaxProfile(name="EU RC", jurisdiction="EU", tax_rate=Decimal("20.000"), is_reverse_charge=True)
    seller = TaxProfile(name="Local 7", jurisdiction="WA", tax_rate=Decimal("7.000"))
    db_session.add_all([rc, seller])
    customer = Customer(name="RC Cust", email="rc@x.x")
    channel = SalesChannel(name="Web")
    db_session.add_all([customer, channel])
    await db_session.flush()
    db_session.add(Sale(
        date=datetime.date(2026, 4, 1), customer_id=customer.id, channel_id=channel.id,
        tax_profile_id=rc.id, tax_treatment="seller_collected",
        subtotal=Decimal("100"), tax_collected=Decimal("20"),
        shipping_cost=Decimal("0"), platform_fees=Decimal("0"),
        total=Decimal("120"), net_revenue=Decimal("100"), sale_number="SAL-2",
        status="completed",
    ))
    db_session.add(Sale(
        date=datetime.date(2026, 4, 2), customer_id=customer.id, channel_id=channel.id,
        tax_profile_id=seller.id, tax_treatment="seller_collected",
        subtotal=Decimal("100"), tax_collected=Decimal("7"),
        shipping_cost=Decimal("0"), platform_fees=Decimal("0"),
        total=Decimal("107"), net_revenue=Decimal("100"), sale_number="SAL-3",
        status="completed",
    ))
    await db_session.commit()
    r = await client.get(
        "/api/v1/tax/reports/liability",
        params={"date_from": "2026-04-01", "date_to": "2026-04-30"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    by_name = {row["tax_profile_name"]: row for row in body["rows"]}
    # Reverse-charge profile: rc_in = rc_out = 20, seller_collected = 0
    rc_row = by_name["EU RC"]
    assert rc_row["is_reverse_charge"] is True
    assert Decimal(rc_row["reverse_charged_in"]) == Decimal("20")
    assert Decimal(rc_row["reverse_charged_out"]) == Decimal("20")
    assert Decimal(rc_row["seller_collected"]) == Decimal("0")
    # Local profile: seller_collected = 7, no reverse-charge
    local_row = by_name["Local 7"]
    assert local_row["is_reverse_charge"] is False
    assert Decimal(local_row["seller_collected"]) == Decimal("7")
    # Totals roll up
    assert Decimal(body["total_reverse_charged_in"]) == Decimal("20")
    assert Decimal(body["total_seller_collected"]) == Decimal("7")
