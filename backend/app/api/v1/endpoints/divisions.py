from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.models.division import Division, Project


router = APIRouter(tags=["DivisionsProjects"])


# ---------- divisions ----------


class DivisionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    notes: str | None = None


class DivisionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None
    notes: str | None = None


class DivisionResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    notes: str | None


@router.get("/divisions", response_model=list[DivisionResponse], summary="List divisions")
async def list_divisions(user: CurrentUser, db: DB, include_inactive: bool = False):
    stmt = select(Division).order_by(Division.name)
    if not include_inactive:
        stmt = stmt.where(Division.is_active == True)  # noqa: E712
    rows = (await db.execute(stmt)).scalars().all()
    return [DivisionResponse(id=r.id, name=r.name, is_active=r.is_active, notes=r.notes) for r in rows]


@router.post("/divisions", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED, summary="Create a division")
async def create_division(body: DivisionCreate, user: CurrentUser, db: DB):
    existing = (await db.execute(select(Division).where(Division.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Division '{body.name}' already exists")
    d = Division(name=body.name, notes=body.notes)
    db.add(d)
    await db.commit()
    return DivisionResponse(id=d.id, name=d.name, is_active=d.is_active, notes=d.notes)


@router.patch("/divisions/{division_id}", response_model=DivisionResponse, summary="Update a division")
async def update_division(division_id: uuid.UUID, body: DivisionUpdate, user: CurrentUser, db: DB):
    d = (await db.execute(select(Division).where(Division.id == division_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Division not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(d, k, v)
    await db.commit()
    return DivisionResponse(id=d.id, name=d.name, is_active=d.is_active, notes=d.notes)


@router.delete("/divisions/{division_id}", status_code=204, summary="Delete a division")
async def delete_division(division_id: uuid.UUID, user: CurrentUser, db: DB):
    d = (await db.execute(select(Division).where(Division.id == division_id))).scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404, detail="Division not found")
    await db.delete(d)
    await db.commit()


# ---------- projects ----------


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    start_on: date | None = None
    end_on: date | None = None
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    status: Literal["active", "archived"] | None = None
    start_on: date | None = None
    end_on: date | None = None
    notes: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    start_on: date | None
    end_on: date | None
    notes: str | None


@router.get("/projects", response_model=list[ProjectResponse], summary="List projects")
async def list_projects(user: CurrentUser, db: DB, include_archived: bool = False):
    stmt = select(Project).order_by(Project.name)
    if not include_archived:
        stmt = stmt.where(Project.status == "active")
    rows = (await db.execute(stmt)).scalars().all()
    return [
        ProjectResponse(
            id=r.id, name=r.name, status=r.status,
            start_on=r.start_on, end_on=r.end_on, notes=r.notes,
        )
        for r in rows
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, summary="Create a project")
async def create_project(body: ProjectCreate, user: CurrentUser, db: DB):
    existing = (await db.execute(select(Project).where(Project.name == body.name))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Project '{body.name}' already exists")
    p = Project(name=body.name, start_on=body.start_on, end_on=body.end_on, notes=body.notes)
    db.add(p)
    await db.commit()
    return ProjectResponse(
        id=p.id, name=p.name, status=p.status,
        start_on=p.start_on, end_on=p.end_on, notes=p.notes,
    )


@router.patch("/projects/{project_id}", response_model=ProjectResponse, summary="Update a project")
async def update_project(project_id: uuid.UUID, body: ProjectUpdate, user: CurrentUser, db: DB):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    return ProjectResponse(
        id=p.id, name=p.name, status=p.status,
        start_on=p.start_on, end_on=p.end_on, notes=p.notes,
    )


@router.delete("/projects/{project_id}", status_code=204, summary="Delete a project")
async def delete_project(project_id: uuid.UUID, user: CurrentUser, db: DB):
    p = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(p)
    await db.commit()
