from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentAdmin
from app.models.approval_request import ApprovalRequest
from app.models.product import Product
from app.models.sale import Sale
from app.schemas.approval import ApprovalDecisionBody, ApprovalRequestResponse
from app.services.audit_service import create_audit_log, snapshot_model
from app.services.inventory_service import adjust_stock
from app.services.sales_service import restore_inventory_for_refund

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", response_model=list[ApprovalRequestResponse], summary="List approval requests (admin only)")
async def list_approvals(admin: CurrentAdmin, db: DB, status_filter: str | None = Query(None)):
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{approval_id}/approve", response_model=ApprovalRequestResponse, summary="Approve request (admin only)")
async def approve_request(approval_id: uuid.UUID, body: ApprovalDecisionBody, admin: CurrentAdmin, db: DB):
    request = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request is not pending")

    if request.action_type == "inventory_adjustment":
        payload = request.request_payload
        product = (await db.execute(select(Product).where(Product.id == payload["product_id"]))).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found for approval execution")
        before = snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])
        txn = await adjust_stock(
            db=db,
            product_id=product.id,
            txn_type=payload["type"],
            quantity=payload["quantity"],
            unit_cost=Decimal(payload["unit_cost"]),
            notes=payload.get("notes"),
            user_id=admin.id,
        )
        await db.flush()
        await db.refresh(product)
        await create_audit_log(
            db,
            actor_user_id=admin.id,
            entity_type="inventory_transaction",
            entity_id=str(txn.id),
            action="approve_and_execute",
            before_snapshot={"product_id": str(product.id), **before},
            after_snapshot={"product_id": str(product.id), **snapshot_model(product, ["stock_qty", "unit_cost", "reorder_point"])},
            reason=request.reason,
        )
    elif request.action_type == "sale_refund":
        sale_id = request.request_payload.get("sale_id")
        try:
            sale_uuid = uuid.UUID(str(sale_id))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Approval request contains an invalid sale reference") from exc
        sale = (await db.execute(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_uuid))).scalar_one_or_none()
        if not sale:
            raise HTTPException(status_code=404, detail="Sale not found for approval execution")
        if sale.status != "refunded":
            before = snapshot_model(sale, ["status", "total", "customer_name"])
            sale.status = "refunded"
            await restore_inventory_for_refund(db, sale, admin.id)
            await create_audit_log(
                db,
                actor_user_id=admin.id,
                entity_type="sale",
                entity_id=str(sale.id),
                action="approve_and_refund",
                before_snapshot=before,
                after_snapshot=snapshot_model(sale, ["status", "total", "customer_name"]),
                reason=request.reason,
            )

    request.status = "approved"
    request.approved_by_user_id = admin.id
    request.decision_notes = body.decision_notes
    request.decided_at = datetime.datetime.now(datetime.timezone.utc)
    await create_audit_log(
        db,
        actor_user_id=admin.id,
        entity_type="approval_request",
        entity_id=str(request.id),
        action="approve",
        after_snapshot={"action_type": request.action_type, "entity_type": request.entity_type, "entity_id": request.entity_id, "status": request.status},
        reason=request.reason,
    )
    await db.commit()
    await db.refresh(request)
    return request


@router.post("/{approval_id}/reject", response_model=ApprovalRequestResponse, summary="Reject request (admin only)")
async def reject_request(approval_id: uuid.UUID, body: ApprovalDecisionBody, admin: CurrentAdmin, db: DB):
    request = (await db.execute(select(ApprovalRequest).where(ApprovalRequest.id == approval_id))).scalar_one_or_none()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Approval request is not pending")
    request.status = "rejected"
    request.approved_by_user_id = admin.id
    request.decision_notes = body.decision_notes
    request.decided_at = datetime.datetime.now(datetime.timezone.utc)
    await create_audit_log(
        db,
        actor_user_id=admin.id,
        entity_type="approval_request",
        entity_id=str(request.id),
        action="reject",
        after_snapshot={"action_type": request.action_type, "entity_type": request.entity_type, "entity_id": request.entity_id, "status": request.status},
        reason=request.reason,
    )
    await db.commit()
    await db.refresh(request)
    return request
