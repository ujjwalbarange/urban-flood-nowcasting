"""Authentication and Authorization Service (Phase 2I-1).

Provides:
- JWT access token generation and validation (HS256)
- PBKDF2 password hashing and verification
- Role-Based Access Control (RBAC): admin, operator, field_worker, citizen
- FastAPI dependencies for protected endpoints
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = structlog.get_logger()

# Security Config
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mufns-mumbai-operational-super-secret-key-2026-sih")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

security = HTTPBearer(auto_error=False)


class User(BaseModel):
    """User representation for authentication context."""
    username: str
    email: Optional[str] = None
    role: str = "citizen"  # admin, operator, field_worker, citizen
    ward_id: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True


class Token(BaseModel):
    """JWT response structure."""
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: str
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# Predefined operational accounts for Municipal Command Center
# Password: "password123" for dev/demonstration environments
def _hash_pwd(password: str, salt: bytes) -> str:
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${h.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt_hex, h_hex = hashed_password.split("$")
        salt = bytes.fromhex(salt_hex)
        expected = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000).hex()
        return secrets.compare_digest(expected, h_hex)
    except Exception:
        return False


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return _hash_pwd(password, salt)


# Default in-memory user registry for municipal operations
_SALT_DEV = bytes.fromhex("102030405060708090a0b0c0d0e0f001")
USERS_DB: Dict[str, Dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "email": "admin@mcgm.gov.in",
        "hashed_password": _hash_pwd("mumbai_admin_2026", _SALT_DEV),
        "role": "admin",
        "full_name": "BMC Disaster Management Commissioner",
        "ward_id": None,
        "is_active": True,
    },
    "operator": {
        "username": "operator",
        "email": "controlroom@mcgm.gov.in",
        "hashed_password": _hash_pwd("operator123", _SALT_DEV),
        "role": "operator",
        "full_name": "Emergency Operations Center Controller",
        "ward_id": "FN",
        "is_active": True,
    },
    "fieldcrew": {
        "username": "fieldcrew",
        "email": "crew.fn@mcgm.gov.in",
        "hashed_password": _hash_pwd("crew123", _SALT_DEV),
        "role": "field_worker",
        "full_name": "Rapid Response Crew Alpha",
        "ward_id": "FN",
        "is_active": True,
    },
    "citizen": {
        "username": "citizen",
        "email": "citizen@mumbai.org",
        "hashed_password": _hash_pwd("citizen123", _SALT_DEV),
        "role": "citizen",
        "full_name": "Registered Citizen Observer",
        "ward_id": "GN",
        "is_active": True,
    },
}


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.PyJWTError as e:
        logger.warning("JWT token decoding failed", error=str(e))
        return None


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    """FastAPI dependency to retrieve authenticated user from Bearer token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    if not username or username not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or credentials invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_info = USERS_DB[username]
    return User(
        username=user_info["username"],
        email=user_info["email"],
        role=user_info["role"],
        ward_id=user_info.get("ward_id"),
        full_name=user_info.get("full_name"),
        is_active=user_info.get("is_active", True),
    )


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """FastAPI dependency for endpoints that allow both public and authenticated users."""
    if not credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if payload and "sub" in payload and payload["sub"] in USERS_DB:
        u = USERS_DB[payload["sub"]]
        return User(
            username=u["username"],
            email=u["email"],
            role=u["role"],
            ward_id=u.get("ward_id"),
            full_name=u.get("full_name"),
        )
    return None


def require_roles(allowed_roles: List[str]):
    """Role-based authorization guard dependency."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles and "admin" not in current_user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {allowed_roles}, but current user has role '{current_user.role}'",
            )
        return current_user
    return role_checker
