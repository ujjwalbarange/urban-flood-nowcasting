"""Authentication API Router.

Exposes endpoints for user authentication, JWT issuance, profile retrieval,
and account verification.

Phase 2I-1: JWT authentication endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from services.api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    USERS_DB,
    User,
    create_access_token,
    get_current_user,
    require_roles,
    verify_password,
    hash_password,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class RegisterRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    email: Optional[str] = Field(None, description="Email address")
    role: str = Field("citizen", description="Role: citizen or field_worker")
    full_name: Optional[str] = Field(None, description="Full Name")
    ward_id: Optional[str] = Field(None, description="Municipal Ward ID")


@router.post("/login")
async def login_json(payload: LoginRequest = Body(...)):
    """Authenticate with username and password, returning a JWT Bearer token."""
    username = payload.username.strip().lower()
    if username not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    user_data = USERS_DB[username]
    if not verify_password(payload.password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token = create_access_token(
        data={"sub": username, "role": user_data["role"], "ward_id": user_data.get("ward_id")}
    )

    logger.info("User logged in successfully", username=username, role=user_data["role"])
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_seconds": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": user_data["role"],
        "username": username,
        "full_name": user_data.get("full_name"),
    }


@router.post("/token")
async def login_oauth2(form_data: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 compatible token login."""
    req = LoginRequest(username=form_data.username, password=form_data.password)
    return await login_json(req)


@router.get("/me", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return current_user


@router.post("/register")
async def register_account(payload: RegisterRequest = Body(...)):
    """Register a new citizen or field worker account."""
    uname = payload.username.strip().lower()
    if uname in USERS_DB:
        raise HTTPException(status_code=400, detail="Username already registered")

    role = payload.role.lower()
    if role not in ("citizen", "field_worker"):
        role = "citizen"

    USERS_DB[uname] = {
        "username": uname,
        "email": payload.email,
        "hashed_password": hash_password(payload.password),
        "role": role,
        "full_name": payload.full_name or uname.capitalize(),
        "ward_id": payload.ward_id,
        "is_active": True,
    }

    access_token = create_access_token(data={"sub": uname, "role": role, "ward_id": payload.ward_id})
    return {
        "message": f"Account {uname} successfully registered",
        "access_token": access_token,
        "token_type": "bearer",
        "role": role,
        "username": uname,
    }


@router.get("/users")
async def list_users(admin_user: User = Depends(require_roles(["admin"]))):
    """List system accounts (requires admin privilege)."""
    return [
        {
            "username": u["username"],
            "email": u["email"],
            "role": u["role"],
            "full_name": u.get("full_name"),
            "ward_id": u.get("ward_id"),
        }
        for u in USERS_DB.values()
    ]
