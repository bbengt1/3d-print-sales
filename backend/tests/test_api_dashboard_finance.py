from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.bill import Bill
from app.models.invoice import Invoice
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.marketplace_settlement import MarketplaceSettlement
from app.models.material_receipt import MaterialReceipt
from app.models.material import Material
from app.models.sales_channel import SalesChannel
from app.services.accounting_service import ensure_accounting_period, seed_chart_of_accounts


@pytest.mark.asyncio
async def test_finance_dashboard_summary(client, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key='2026-03',
        name='March 2026',
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    accounts = (await db_session.execute(__import__('sqlalchemy').select(Account))).scalars().all()
    cash = next(a for a in accounts if a.code == '1000')
    sales = next(a for a in accounts if a.code == '4000')
    cogs = next(a for a in accounts if a.code == '5000')
    expense = next(a for a in accounts if a.code == '6000')
    tax = next(a for a in accounts if a.code == '2100')

    material = Material(name='PLA', brand='Generic', spool_weight_g=Decimal('1000'), spool_price=Decimal('20'), net_usable_g=Decimal('950'), cost_per_g=Decimal('0.021053'))
    channel = SalesChannel(name='Etsy', platform_fee_pct=Decimal('6.5'), fixed_fee=Decimal('0.20'))
    db_session.add_all([material, channel])
    await db_session.flush()

    today = date.today()
    je = JournalEntry(entry_number='JE-DASH-1', entry_date=today, accounting_period_id=period.id, status='posted', memo='Finance dashboard seed')
    db_session.add(je)
    await db_session.flush()
    db_session.add_all([
        JournalLine(journal_entry_id=je.id, account_id=cash.id, line_number=1, entry_type='debit', amount=Decimal('1000.00')),
        JournalLine(journal_entry_id=je.id, account_id=sales.id, line_number=2, entry_type='credit', amount=Decimal('500.00')),
        JournalLine(journal_entry_id=je.id, account_id=cogs.id, line_number=3, entry_type='debit', amount=Decimal('200.00')),
        JournalLine(journal_entry_id=je.id, account_id=expense.id, line_number=4, entry_type='debit', amount=Decimal('100.00')),
        JournalLine(journal_entry_id=je.id, account_id=tax.id, line_number=5, entry_type='credit', amount=Decimal('50.00')),
    ])

    db_session.add(Invoice(invoice_number='INV-DASH-1', issue_date=today, due_date=today, subtotal=Decimal('100.00'), total_due=Decimal('100.00'), balance_due=Decimal('100.00'), status='sent'))
    db_session.add(Bill(account_id=expense.id, description='Vendor bill', issue_date=today, due_date=today, amount=Decimal('80.00'), amount_paid=Decimal('20.00'), status='partially_paid'))
    db_session.add(MaterialReceipt(material_id=material.id, vendor_name='Vendor', purchase_date=today, quantity_purchased_g=Decimal('1000.00'), quantity_remaining_g=Decimal('500.00'), unit_cost_per_g=Decimal('0.020000'), landed_cost_total=Decimal('1.00'), landed_cost_per_g=Decimal('0.025000'), total_cost=Decimal('25.00')))
    db_session.add(MarketplaceSettlement(settlement_number='SET-DASH-1', channel_id=channel.id, period_start=today, period_end=today, payout_date=today + timedelta(days=2), gross_sales=Decimal('100.00'), marketplace_fees=Decimal('10.00'), adjustments=Decimal('0.00'), reserves_held=Decimal('5.00'), net_deposit=Decimal('85.00'), expected_net=Decimal('85.00'), discrepancy_amount=Decimal('0.00')))
    await db_session.commit()

    resp = await client.get('/api/v1/dashboard/finance-summary')
    assert resp.status_code == 200
    data = resp.json()
    assert float(data['cash_on_hand']) == 1000.0
    assert float(data['unpaid_invoices']) == 100.0
    assert float(data['unpaid_bills']) == 60.0
    assert float(data['current_month_net_income']) == 200.0
    assert float(data['tax_payable']) == 50.0
    assert float(data['payouts_in_transit']) == 85.0
