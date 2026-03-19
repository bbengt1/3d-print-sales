from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.models.customer import Customer
from app.models.job import Job
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "",
    response_model=list[CustomerResponse],
    summary="List customers",
    description="Returns customers with job counts. Supports search by name/email and pagination.",
)
async def list_customers(
    db: DB,
    search: str | None = Query(None, description="Search by name or email"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
):
    stmt = (
        select(Customer, func.count(Job.id).label("job_count"))
        .outerjoin(Job, (Job.customer_id == Customer.id) & (Job.is_deleted == False))
        .group_by(Customer.id)
    )
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            Customer.name.ilike(pattern) | Customer.email.ilike(pattern)
        )
    stmt = stmt.order_by(Customer.name).offset(skip).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        CustomerResponse(
            id=c.id,
            name=c.name,
            email=c.email,
            phone=c.phone,
            notes=c.notes,
            job_count=count,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c, count in rows
    ]


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer by ID",
    description="Retrieve a single customer with their total job count.",
)
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
        id=c.id,
        name=c.name,
        email=c.email,
        phone=c.phone,
        notes=c.notes,
        job_count=count,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    summary="Create a customer",
    description="Add a new customer record. Customers can be linked to jobs for tracking.",
)
async def create_customer(body: CustomerCreate, user: CurrentUser, db: DB):
    customer = Customer(**body.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        notes=customer.notes,
        job_count=0,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update a customer",
    description="Update one or more fields of a customer record.",
)
async def update_customer(customer_id: uuid.UUID, body: CustomerUpdate, user: CurrentUser, db: DB):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)

    count_stmt = (
        select(func.count(Job.id))
        .where(Job.customer_id == customer_id, Job.is_deleted == False)
    )
    count_result = await db.execute(count_stmt)
    job_count = count_result.scalar() or 0

    return CustomerResponse(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        notes=customer.notes,
        job_count=job_count,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
    )


@router.delete(
    "/{customer_id}",
    status_code=204,
    summary="Delete a customer",
    description="Permanently delete a customer record. Jobs linked to this customer will retain the customer_name field.",
)
async def delete_customer(customer_id: uuid.UUID, user: CurrentUser, db: DB):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    await db.delete(customer)
    await db.commit()
