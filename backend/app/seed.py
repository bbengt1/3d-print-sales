from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings as app_settings
from app.core.database import async_session
from app.core.security import hash_password
from app.models.account import Account
from app.models.material import Material
from app.models.rate import Rate
from app.models.sales_channel import SalesChannel
from app.models.setting import Setting
from app.models.user import User
from app.services.accounting_service import seed_chart_of_accounts

SETTINGS_DATA = [
    ("currency", "USD", "Currency code"),
    ("default_profit_margin_pct", "40", "Target markup on total cost"),
    ("platform_fee_pct", "9.5", "Etsy/Amazon/etc."),
    ("fixed_fee_per_order", "0.45", "Per-transaction fee"),
    ("sales_tax_pct", "0", "Set if you collect tax"),
    ("electricity_cost_per_kwh", "0.18", "Check your utility bill"),
    ("printer_power_draw_watts", "120", "Average draw while printing"),
    ("failure_rate_pct", "5", "Buffer for failed prints"),
    ("packaging_cost_per_order", "1.25", "Boxes, tape, padding"),
    ("shipping_charged_to_customer", "0", "0 = free shipping model"),
]

MATERIALS_DATA = [
    ("PLA", "Generic", 1000, 20, 950, "Standard PLA spool", True),
    ("PETG", "Generic", 1000, 24, 950, "Stronger, slight flex", True),
    ("TPU", "Generic", 1000, 30, 900, "Flexible filament", True),
    ("ABS", "Generic", 1000, 22, 920, "Heat resistant", False),
    ("PLA+", "eSUN", 1000, 25, 950, "Enhanced PLA", True),
]

RATES_DATA = [
    ("Labor rate", Decimal("25"), "$/hour", "Hands-on + design time"),
    ("Machine rate", Decimal("1.5"), "$/hour", "Wear & depreciation"),
    ("Overhead %", Decimal("10"), "%", "Rent, insurance, misc"),
]


async def run_seed():
    async with async_session() as db:
        # Seed settings
        result = await db.execute(select(Setting).limit(1))
        if not result.scalar_one_or_none():
            for key, value, notes in SETTINGS_DATA:
                db.add(Setting(key=key, value=value, notes=notes))
            await db.commit()

        # Seed materials
        result = await db.execute(select(Material).limit(1))
        if not result.scalar_one_or_none():
            for name, brand, weight, price, usable, notes, active in MATERIALS_DATA:
                cost_per_g = Decimal(str(price)) / Decimal(str(usable))
                db.add(Material(
                    name=name, brand=brand,
                    spool_weight_g=Decimal(str(weight)),
                    spool_price=Decimal(str(price)),
                    net_usable_g=Decimal(str(usable)),
                    cost_per_g=cost_per_g,
                    notes=notes, active=active,
                ))
            await db.commit()

        # Seed rates
        result = await db.execute(select(Rate).limit(1))
        if not result.scalar_one_or_none():
            for name, value, unit, notes in RATES_DATA:
                db.add(Rate(name=name, value=value, unit=unit, notes=notes))
            await db.commit()

        # Seed sales channels
        result = await db.execute(select(SalesChannel).limit(1))
        if not result.scalar_one_or_none():
            channels = [
                SalesChannel(name="Etsy", platform_fee_pct=Decimal("6.5"), fixed_fee=Decimal("0.20")),
                SalesChannel(name="Amazon Handmade", platform_fee_pct=Decimal("15"), fixed_fee=Decimal("0")),
                SalesChannel(name="Direct Sale", platform_fee_pct=Decimal("0"), fixed_fee=Decimal("0")),
                SalesChannel(name="Craft Fair", platform_fee_pct=Decimal("0"), fixed_fee=Decimal("0")),
                SalesChannel(name="POS", platform_fee_pct=Decimal("0"), fixed_fee=Decimal("0")),
            ]
            for ch in channels:
                db.add(ch)
            await db.commit()

        # Seed chart of accounts
        result = await db.execute(select(Account).limit(1))
        if not result.scalar_one_or_none():
            await seed_chart_of_accounts(db)

        # Seed admin user
        result = await db.execute(
            select(User).where(User.email == app_settings.ADMIN_EMAIL)
        )
        if not result.scalar_one_or_none():
            db.add(User(
                email=app_settings.ADMIN_EMAIL,
                hashed_password=hash_password(app_settings.ADMIN_PASSWORD),
                full_name="Admin",
                role="admin",
            ))
            await db.commit()
