from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field


class VendorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    contact_name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=500)
    is_active: bool = True


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    contact_name: str | None = Field(None, max_length=120)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=500)
    is_active: bool | None = None


class VendorResponse(BaseModel):
    id: uuid.UUID
    name: str
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ExpenseCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=255)
    account_id: uuid.UUID
    is_active: bool = True


class ExpenseCategoryCreate(ExpenseCategoryBase):
    pass


class ExpenseCategoryUpdate(BaseModel):
    description: str | None = Field(None, max_length=255)
    account_id: uuid.UUID | None = None
    is_active: bool | None = None


class ExpenseCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    account_id: uuid.UUID
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
