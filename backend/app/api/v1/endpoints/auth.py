from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DB, CurrentAdmin, CurrentUser
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user",
    description="Validates email and password, returns a JWT access token.",
)
async def login(body: LoginRequest, db: DB):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(current_user: CurrentUser):
    return current_user


@router.put(
    "/me/password",
    response_model=UserResponse,
    summary="Change password",
    description="Change the current user's password. Requires the current password for verification.",
)
async def change_password(body: PasswordChange, current_user: CurrentUser, db: DB):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    await db.refresh(current_user)
    return current_user


# --- Admin-only user management ---


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user (admin only)",
    description="Create a new user account. Only administrators can create accounts.",
)
async def register(body: UserCreate, admin: CurrentAdmin, db: DB):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List users (admin only)",
    description="Returns all user accounts. Only administrators can view the user list.",
)
async def list_users(
    admin: CurrentAdmin,
    db: DB,
    is_active: bool | None = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    stmt = select(User)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    result = await db.execute(stmt.order_by(User.created_at.desc()).offset(skip).limit(limit))
    return result.scalars().all()


@router.get(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (admin only)",
    description="Retrieve a single user account.",
)
async def get_user(user_id: uuid.UUID, admin: CurrentAdmin, db: DB):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="Update user (admin only)",
    description="Update a user's profile, role, or active status. Admins cannot deactivate themselves.",
)
async def update_user(user_id: uuid.UUID, body: UserUpdate, admin: CurrentAdmin, db: DB):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_active is False and user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    if body.role and body.role.value != "admin" and user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    if body.email and body.email != user.email:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "role":
            setattr(user, field, value.value)
        else:
            setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete(
    "/users/{user_id}",
    status_code=204,
    summary="Deactivate user (admin only)",
    description="Soft-deletes a user by setting is_active=false. Admins cannot deactivate themselves.",
)
async def deactivate_user(user_id: uuid.UUID, admin: CurrentAdmin, db: DB):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    user.is_active = False
    await db.commit()
