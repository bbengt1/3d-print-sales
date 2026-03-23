from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.accounting_service import ensure_accounting_period, seed_chart_of_accounts


@pytest.mark.asyncio
async def test_formal_financial_statements(client, auth_headers, db_session: AsyncSession):
    await seed_chart_of_accounts(db_session)
    period = await ensure_accounting_period(
        db_session,
        period_key="2026-03",
        name="March 2026",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    accounts = (await client.get('/api/v1/accounting/accounts', headers=auth_headers)).json()
    cash = next(a for a in accounts if a['code'] == '1000')
    ar = next(a for a in accounts if a['code'] == '1100')
    ap = next(a for a in accounts if a['code'] == '2000')
    equity = next(a for a in accounts if a['code'] == '3000')
    sales = next(a for a in accounts if a['code'] == '4000')
    cogs = next(a for a in accounts if a['code'] == '5000')
    expense = next(a for a in accounts if a['code'] == '6000')

    period_id = str(period.id)

    entries = [
        {
            'entry_date': '2026-03-01',
            'accounting_period_id': period_id,
            'memo': 'Owner funding',
            'lines': [
                {'account_id': cash['id'], 'entry_type': 'debit', 'amount': '1000.00'},
                {'account_id': equity['id'], 'entry_type': 'credit', 'amount': '1000.00'},
            ],
        },
        {
            'entry_date': '2026-03-10',
            'accounting_period_id': period_id,
            'memo': 'Sale on account',
            'lines': [
                {'account_id': ar['id'], 'entry_type': 'debit', 'amount': '300.00'},
                {'account_id': sales['id'], 'entry_type': 'credit', 'amount': '300.00'},
            ],
        },
        {
            'entry_date': '2026-03-10',
            'accounting_period_id': period_id,
            'memo': 'COGS recognition',
            'lines': [
                {'account_id': cogs['id'], 'entry_type': 'debit', 'amount': '120.00'},
                {'account_id': cash['id'], 'entry_type': 'credit', 'amount': '120.00'},
            ],
        },
        {
            'entry_date': '2026-03-12',
            'accounting_period_id': period_id,
            'memo': 'Expense on account',
            'lines': [
                {'account_id': expense['id'], 'entry_type': 'debit', 'amount': '80.00'},
                {'account_id': ap['id'], 'entry_type': 'credit', 'amount': '80.00'},
            ],
        },
    ]
    for payload in entries:
        resp = await client.post('/api/v1/accounting/journal-entries', headers=auth_headers, json=payload)
        assert resp.status_code == 201

    bs = await client.get('/api/v1/reports/balance-sheet', headers=auth_headers, params={'as_of_date': '2026-03-31'})
    assert bs.status_code == 200
    bs_data = bs.json()
    assert float(bs_data['assets']['total']) == 1180.0
    assert float(bs_data['liabilities']['total']) == 80.0
    assert float(bs_data['equity']['total']) == 1000.0
    assert bs_data['is_balanced'] is False

    accrual = await client.get('/api/v1/reports/pl-accrual', headers=auth_headers, params={'date_from': '2026-03-01', 'date_to': '2026-03-31'})
    assert accrual.status_code == 200
    assert float(accrual.json()['revenue']['total']) == 300.0
    assert float(accrual.json()['cogs']['total']) == 120.0
    assert float(accrual.json()['expenses']['total']) == 80.0
    assert float(accrual.json()['net_income']) == 100.0

    cash_pl = await client.get('/api/v1/reports/pl-cash', headers=auth_headers, params={'date_from': '2026-03-01', 'date_to': '2026-03-31'})
    assert cash_pl.status_code == 200
    assert cash_pl.json()['basis'] == 'cash'

    cash_flow = await client.get('/api/v1/reports/cash-flow', headers=auth_headers, params={'date_from': '2026-03-01', 'date_to': '2026-03-31'})
    assert cash_flow.status_code == 200
    assert 'net_change_in_cash' in cash_flow.json()
