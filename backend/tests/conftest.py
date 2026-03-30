from __future__ import annotations

import os
import uuid
from decimal import Decimal

os.environ["TESTING"] = "true"
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.account import Account
from app.models.customer import Customer
from app.models.material import Material
from app.models.material_receipt import MaterialReceipt
from app.models.rate import Rate
from app.models.setting import Setting
from app.models.user import User
from app.models.printer_history_event import PrinterHistoryEvent  # noqa: F401
from app.services.accounting_service import seed_chart_of_accounts

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSession() as session:
        existing_account = await session.execute(select(Account.id).limit(1))
        if existing_account.scalar_one_or_none() is None:
            await seed_chart_of_accounts(session)
        yield session


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, db_session: AsyncSession):
    """Admin auth headers."""
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpass"),
        full_name="Test Admin",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "testpass"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def user_headers(client: AsyncClient, db_session: AsyncSession):
    """Non-admin user auth headers."""
    user = User(
        email="regular@example.com",
        hashed_password=hash_password("userpass"),
        full_name="Regular User",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "regular@example.com", "password": "userpass"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def seed_settings(db_session: AsyncSession):
    settings_data = [
        ("currency", "USD", "Currency"),
        ("default_profit_margin_pct", "40", "Target markup"),
        ("platform_fee_pct", "9.5", "Platform fee"),
        ("fixed_fee_per_order", "0.45", "Per-transaction fee"),
        ("sales_tax_pct", "0", "Sales tax"),
        ("electricity_cost_per_kwh", "0.18", "Electricity rate"),
        ("printer_power_draw_watts", "120", "Printer power"),
        ("failure_rate_pct", "5", "Failure buffer"),
        ("packaging_cost_per_order", "1.25", "Packaging cost"),
        ("shipping_charged_to_customer", "0", "Shipping model"),
    ]
    for key, value, notes in settings_data:
        db_session.add(Setting(key=key, value=value, notes=notes))
    await db_session.commit()


@pytest_asyncio.fixture
async def seed_rates(db_session: AsyncSession):
    rates = [
        ("Labor rate", Decimal("25"), "$/hour", "Hands-on + design time"),
        ("Machine rate", Decimal("1.5"), "$/hour", "Wear & depreciation"),
        ("Overhead %", Decimal("10"), "%", "Rent, insurance, misc"),
    ]
    for name, value, unit, notes in rates:
        db_session.add(Rate(name=name, value=value, unit=unit, notes=notes))
    await db_session.commit()


@pytest_asyncio.fixture
async def seed_material(db_session: AsyncSession) -> Material:
    mat = Material(
        name="PLA",
        brand="Generic",
        spool_weight_g=Decimal("1000"),
        spool_price=Decimal("20"),
        net_usable_g=Decimal("950"),
        cost_per_g=Decimal("20") / Decimal("950"),
    )
    db_session.add(mat)
    await db_session.commit()
    await db_session.refresh(mat)
    return mat
