from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models.customer import Customer
from app.models.job import Job

router = APIRouter(prefix="/customers", tags=["Customers"])


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    job_count: int = 0

    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    db: DB,
    search: str | None = Query(None),
    skip: int = 0,
    limit: int = 50,
):
    stmt = select(
        Customer, func.count(Job.id).label("job_count")
    ).outerjoin(Job, (Job.customer_id == Customer.id) & (Job.is_deleted == False)).group_by(Customer.id)

    if search:
        stmt = stmt.where(Customer.name.ilike(f"%{search}%"))
    stmt = stmt.order_by(Customer.name).offset(skip).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        CustomerResponse(
            id=c.id, name=c.name, email=c.email,
            phone=c.phone, notes=c.notes, job_count=count,
        )
        for c, count in rows
    ]


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(customer_id: uuid.UUID, db: DB):
    stmt = (
        select(Customer, func.count(Job.id).label("job_count"))
        .outerjoin(Job, (Job.customer_id == Customer.id) & (Job.is_deleted == False))
        .where(Customer.id == customer_id)
        .group_by(Customer.id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    c, count = row
    return CustomerResponse(
        id=c.id, name=c.name, email=c.email,
        phone=c.phone, notes=c.notes, job_count=count,
    )


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(body: CustomerCreate, db: DB):
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse(**customer.__dict__, job_count=0)


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(customer_id: uuid.UUID, body: CustomerUpdate, db: DB):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
async def delete_customer(customer_id: uuid.UUID, db: DB):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(customer)
    await db.commit()
