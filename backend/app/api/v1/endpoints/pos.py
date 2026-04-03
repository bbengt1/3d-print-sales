from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser
from app.api.v1.endpoints.sales import _to_sale_response
from app.models.sale import Sale
from app.schemas.sale import POSCheckoutCreate, SaleResponse
from app.services.audit_service import create_audit_log
from app.services.sales_service import (
    InsufficientStockError,
    create_sale_with_items,
    get_or_create_sales_channel,
)

POS_CHANNEL_NAME = "POS"

router = APIRouter(prefix="/pos", tags=["Sales"])


@router.post(
    "/checkout",
    response_model=SaleResponse,
    status_code=201,
    summary="Create a POS checkout sale",
    description=(
        "Creates a point-of-sale checkout using the standard sales tables and inventory path. "
        "POS sales are identified by the dedicated POS sales channel and stored as normal sales."
    ),
)
async def pos_checkout(body: POSCheckoutCreate, user: CurrentUser, db: DB):
    channel = await get_or_create_sales_channel(db, name=POS_CHANNEL_NAME)

    try:
        sale = await create_sale_with_items(
            db,
            user_id=user.id,
            date=body.date,
            customer_id=body.customer_id,
            customer_name=body.customer_name,
            channel_id=channel.id,
            tax_profile_id=body.tax_profile_id,
            tax_treatment=body.tax_treatment,
            shipping_charged=0,
            shipping_cost=0,
            tax_collected=body.tax_collected,
            payment_method=body.payment_method,
            tracking_number=None,
            notes=body.notes,
            status="paid",
            items=body.items,
            enforce_stock_availability=True,
        )
    except InsufficientStockError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await create_audit_log(
        db,
        actor_user_id=user.id,
        entity_type="sale",
        entity_id=str(sale.id),
        action="pos_checkout",
        after_snapshot={
            "sale_number": sale.sale_number,
            "status": sale.status,
            "total": sale.total,
            "customer_name": sale.customer_name,
            "payment_method": sale.payment_method,
            "channel": POS_CHANNEL_NAME,
        },
        reason=body.notes,
    )
    await db.commit()

    result = await db.execute(
        select(Sale).options(selectinload(Sale.items), selectinload(Sale.channel)).where(Sale.id == sale.id)
    )
    return _to_sale_response(result.scalar_one())
