from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import DB, CurrentUser
from app.services.merge_service import (
    MergeError,
    merge_materials,
    merge_products,
)


router = APIRouter(prefix="/merge", tags=["Merge"])


class MergeRequest(BaseModel):
    survivor_id: uuid.UUID
    duplicate_ids: list[uuid.UUID] = Field(..., min_length=1)


@router.post(
    "/{scope}",
    summary="#262 P2: merge duplicate items into a survivor (scope: material|product)",
)
async def merge_ep(scope: Literal["material", "product"], body: MergeRequest, user: CurrentUser, db: DB):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admins only")
    try:
        if scope == "material":
            result = await merge_materials(
                db,
                survivor_id=body.survivor_id,
                duplicate_ids=body.duplicate_ids,
                actor_user_id=user.id,
            )
        else:
            result = await merge_products(
                db,
                survivor_id=body.survivor_id,
                duplicate_ids=body.duplicate_ids,
                actor_user_id=user.id,
            )
    except MergeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await db.commit()
    return result
