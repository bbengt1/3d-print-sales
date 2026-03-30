from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.printer import Printer
from app.models.printer_history_event import PrinterHistoryEvent
from app.models.user import User
from app.services.audit_service import _json_safe


async def create_printer_history_event(
    db: AsyncSession,
    *,
    printer_id: uuid.UUID,
    event_type: str,
    title: str,
    description: str | None = None,
    job_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> PrinterHistoryEvent:
    event = PrinterHistoryEvent(
        printer_id=printer_id,
        job_id=job_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        title=title,
        description=description,
        event_metadata=_json_safe(metadata),
    )
    db.add(event)
    await db.flush()
    return event


async def list_printer_history_events(db: AsyncSession, printer_id: uuid.UUID, *, limit: int = 25) -> list[PrinterHistoryEvent]:
    result = await db.execute(
        select(PrinterHistoryEvent)
        .options(selectinload(PrinterHistoryEvent.actor), selectinload(PrinterHistoryEvent.job))
        .where(PrinterHistoryEvent.printer_id == printer_id)
        .order_by(PrinterHistoryEvent.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def record_printer_status_change(
    db: AsyncSession,
    *,
    printer: Printer,
    old_status: str | None,
    new_status: str | None,
    actor_user_id: uuid.UUID | None = None,
    source: str = "manual",
) -> PrinterHistoryEvent | None:
    if old_status == new_status:
        return None
    return await create_printer_history_event(
        db,
        printer_id=printer.id,
        actor_user_id=actor_user_id,
        event_type="status_changed",
        title=f"Status changed to {new_status or 'unknown'}",
        description=f"Printer status changed from {old_status or 'unknown'} to {new_status or 'unknown'}.",
        metadata={"from_status": old_status, "to_status": new_status, "source": source},
    )


async def record_job_assignment_change(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    job_number: str,
    product_name: str,
    old_printer: Printer | None,
    new_printer: Printer | None,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    if (old_printer.id if old_printer else None) == (new_printer.id if new_printer else None):
        return

    base_metadata = {
        "job_id": job_id,
        "job_number": job_number,
        "product_name": product_name,
        "from_printer_id": str(old_printer.id) if old_printer else None,
        "from_printer_name": old_printer.name if old_printer else None,
        "to_printer_id": str(new_printer.id) if new_printer else None,
        "to_printer_name": new_printer.name if new_printer else None,
    }

    if old_printer and new_printer:
        await create_printer_history_event(
            db,
            printer_id=old_printer.id,
            job_id=job_id,
            actor_user_id=actor_user_id,
            event_type="job_reassigned_from",
            title=f"Job {job_number} reassigned away",
            description=f"{product_name} was moved from {old_printer.name} to {new_printer.name}.",
            metadata=base_metadata,
        )
        await create_printer_history_event(
            db,
            printer_id=new_printer.id,
            job_id=job_id,
            actor_user_id=actor_user_id,
            event_type="job_reassigned_to",
            title=f"Job {job_number} reassigned here",
            description=f"{product_name} was moved from {old_printer.name} to {new_printer.name}.",
            metadata=base_metadata,
        )
        return

    if new_printer:
        await create_printer_history_event(
            db,
            printer_id=new_printer.id,
            job_id=job_id,
            actor_user_id=actor_user_id,
            event_type="job_assigned",
            title=f"Job {job_number} assigned",
            description=f"{product_name} was assigned to {new_printer.name}.",
            metadata=base_metadata,
        )
        return

    if old_printer:
        await create_printer_history_event(
            db,
            printer_id=old_printer.id,
            job_id=job_id,
            actor_user_id=actor_user_id,
            event_type="job_unassigned",
            title=f"Job {job_number} unassigned",
            description=f"{product_name} was unassigned from {old_printer.name}.",
            metadata=base_metadata,
        )


async def get_user_label(db: AsyncSession, user_id: uuid.UUID | None) -> str | None:
    if not user_id:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    return user.full_name or user.email
