import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base
# Import all models so metadata is populated
from app.models.setting import Setting  # noqa
from app.models.material import Material  # noqa
from app.models.rate import Rate  # noqa
from app.models.customer import Customer  # noqa
from app.models.job import Job  # noqa
from app.models.user import User  # noqa
from app.models.product import Product  # noqa
from app.models.inventory_transaction import InventoryTransaction  # noqa
from app.models.sales_channel import SalesChannel  # noqa
from app.models.sale import Sale  # noqa
from app.models.sale_item import SaleItem  # noqa
from app.models.account import Account  # noqa
from app.models.accounting_period import AccountingPeriod  # noqa
from app.models.journal_entry import JournalEntry  # noqa
from app.models.journal_line import JournalLine  # noqa
from app.models.material_receipt import MaterialReceipt  # noqa
from app.models.vendor import Vendor  # noqa
from app.models.expense_category import ExpenseCategory  # noqa
from app.models.bill import Bill  # noqa
from app.models.bill_payment import BillPayment  # noqa
from app.models.recurring_expense import RecurringExpense  # noqa
from app.models.quote import Quote  # noqa
from app.models.invoice import Invoice  # noqa
from app.models.invoice_line import InvoiceLine  # noqa
from app.models.payment import Payment  # noqa
from app.models.customer_credit import CustomerCredit  # noqa
from app.models.tax_profile import TaxProfile  # noqa
from app.models.tax_remittance import TaxRemittance  # noqa
from app.models.marketplace_settlement import MarketplaceSettlement  # noqa
from app.models.settlement_line import SettlementLine  # noqa
from app.models.audit_log import AuditLog  # noqa
from app.models.approval_request import ApprovalRequest  # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
