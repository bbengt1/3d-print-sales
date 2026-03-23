from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill
from app.models.customer import Customer
from app.models.expense_category import ExpenseCategory
from app.models.invoice import Invoice
from app.models.invoice_line import InvoiceLine
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.sales_channel import SalesChannel
from app.models.tax_profile import TaxProfile
from app.models.tax_remittance import TaxRemittance
from app.models.vendor import Vendor
from app.services.accounting_service import seed_chart_of_accounts


@pytest.mark.asyncio
async def test_finance_reports_core_totals(client, auth_headers, db_session: AsyncSession, seed_material: Material):
    await seed_chart_of_accounts(db_session)

    customer = Customer(name="AR Customer", email="ar@example.com")
    vendor = Vendor(name="Vendor A", is_active=True)
    channel = SalesChannel(name="Etsy", platform_fee_pct=Decimal("6.5"), fixed_fee=Decimal("0.20"))
    tax_profile = TaxProfile(name="Texas Direct", jurisdiction="TX", tax_rate=Decimal("8.25"), filing_frequency="monthly", is_active=True)
    db_session.add_all([customer, vendor, channel, tax_profile])
    await db_session.flush()

    invoice = Invoice(
        invoice_number="INV-RPT-1",
        customer_id=customer.id,
        customer_name=customer.name,
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 10),
        subtotal=Decimal("100.00"),
        total_due=Decimal("100.00"),
        balance_due=Decimal("100.00"),
        status="sent",
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(InvoiceLine(invoice_id=invoice.id, description="Print job", quantity=1, unit_price=Decimal("100.00"), line_total=Decimal("100.00")))

    bill = Bill(
        vendor_id=vendor.id,
        account_id=(await db_session.execute(__import__('sqlalchemy').select(__import__('app.models.account', fromlist=['Account']).Account).where(__import__('app.models.account', fromlist=['Account']).Account.code == '6000'))).scalar_one().id,
        bill_number="BILL-RPT-1",
        description="Material purchase",
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 5),
        amount=Decimal("80.00"),
        amount_paid=Decimal("20.00"),
        status="partially_paid",
    )
    db_session.add(bill)

    sale = Sale(
        sale_number="S-RPT-1",
        date=date(2026, 3, 12),
        customer_name="Buyer",
        channel_id=channel.id,
        tax_profile_id=tax_profile.id,
        tax_treatment="seller_collected",
        status="paid",
        subtotal=Decimal("40.00"),
        shipping_charged=Decimal("5.00"),
        shipping_cost=Decimal("3.00"),
        platform_fees=Decimal("2.00"),
        tax_collected=Decimal("3.30"),
        total=Decimal("48.30"),
        net_revenue=Decimal("43.30"),
    )
    db_session.add(sale)
    await db_session.flush()
    db_session.add(SaleItem(sale_id=sale.id, description="Widget", quantity=2, unit_price=Decimal("20.00"), line_total=Decimal("40.00"), unit_cost=Decimal("8.00")))

    receipt = MaterialReceipt(
        material_id=seed_material.id,
        vendor_name="Vendor A",
        purchase_date=date(2026, 3, 2),
        quantity_purchased_g=Decimal("1000.00"),
        quantity_remaining_g=Decimal("600.00"),
        unit_cost_per_g=Decimal("0.020000"),
        landed_cost_total=Decimal("2.00"),
        landed_cost_per_g=Decimal("0.022000"),
        total_cost=Decimal("22.00"),
    )
    db_session.add(receipt)

    remittance = TaxRemittance(
        tax_profile_id=tax_profile.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        remittance_date=date(2026, 4, 20),
        amount=Decimal("1.30"),
    )
    db_session.add(remittance)
    await db_session.commit()

    ar = await client.get('/api/v1/reports/ar-aging', headers=auth_headers, params={'as_of_date': '2026-03-23'})
    assert ar.status_code == 200
    assert float(ar.json()['total_outstanding']) == 100.0

    ap = await client.get('/api/v1/reports/ap-aging', headers=auth_headers, params={'as_of_date': '2026-03-23'})
    assert ap.status_code == 200
    assert float(ap.json()['total_outstanding']) == 60.0

    tax = await client.get('/api/v1/reports/tax-liability', headers=auth_headers)
    assert tax.status_code == 200
    assert float(tax.json()['total_seller_collected']) == 3.3
    assert float(tax.json()['total_outstanding_liability']) == 2.0

    inv = await client.get('/api/v1/reports/inventory-valuation', headers=auth_headers)
    assert inv.status_code == 200
    assert float(inv.json()['total_inventory_value']) == 13.2

    cogs = await client.get('/api/v1/reports/cogs-breakdown', headers=auth_headers)
    assert cogs.status_code == 200
    assert float(cogs.json()['total_cogs']) == 16.0
    assert float(cogs.json()['total_revenue']) == 40.0
