"""Authentication utilities: password hashing, JWT tokens, Google verification."""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel

from .db import get_pool

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT config
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=False)


# --- Pydantic Models ---


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    auth_provider: str
    role: str
    is_verified: bool
    created_at: str


# --- Password Helpers ---


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# --- JWT Helpers ---


def create_access_token(user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token_value() -> str:
    """Generate a random opaque refresh token string."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def hash_token(token: str) -> str:
    """SHA-256 hash for storing refresh tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    """Decode and verify an access JWT. Raises HTTPException on invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# --- Refresh Token DB Operations ---


async def store_refresh_token(
    user_id: str, token: str, user_agent: str = "", ip_address: str = ""
) -> str:
    """Hash and store a refresh token. Returns the token ID."""
    pool = get_pool()
    token_id = uuid.uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, user_agent, ip_address)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            token_id, uuid.UUID(user_id), hash_token(token),
            expires_at, user_agent, ip_address,
        )
    return str(token_id)


async def validate_and_rotate_refresh_token(old_token: str) -> Optional[dict]:
    """Validate a refresh token, revoke it, return user data if valid.

    Implements refresh token rotation with reuse detection.
    """
    pool = get_pool()
    old_hash = hash_token(old_token)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked,
                   u.email, u.role, u.is_active
            FROM refresh_tokens rt
            JOIN users u ON u.id = rt.user_id
            WHERE rt.token_hash = $1
            """,
            old_hash,
        )
        if not row:
            return None
        if row["revoked"]:
            # Token reuse detected — revoke ALL tokens for this user
            await conn.execute(
                "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = $1",
                row["user_id"],
            )
            logger.warning(f"Refresh token reuse detected for user {row['user_id']}")
            return None
        if row["expires_at"] < datetime.now(timezone.utc):
            return None
        if not row["is_active"]:
            return None

        # Revoke the old token
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE id = $1",
            row["id"],
        )

    return {
        "user_id": str(row["user_id"]),
        "email": row["email"],
        "role": row["role"],
    }


async def revoke_all_user_tokens(user_id: str):
    """Revoke all refresh tokens for a user (logout all sessions)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE refresh_tokens SET revoked = TRUE WHERE user_id = $1",
            uuid.UUID(user_id),
        )


# --- Google Token Verification ---


async def verify_google_token(id_token_str: str) -> dict:
    """Verify a Google ID token and return user info."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        if idinfo["iss"] not in ("accounts.google.com", "https://accounts.google.com"):
            raise ValueError("Wrong issuer")
        return idinfo
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")


# --- User DB Helpers ---


async def get_user_by_email(email: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
    return dict(row) if row else None


async def get_user_by_id(user_id: str) -> Optional[dict]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1", uuid.UUID(user_id)
        )
    return dict(row) if row else None


async def create_user(
    email: str,
    hashed_password: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    auth_provider: str = "local",
    provider_id: Optional[str] = None,
    is_verified: bool = False,
) -> dict:
    pool = get_pool()
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (id, email, hashed_password, first_name, last_name,
                               auth_provider, provider_id, role, is_active, is_verified,
                               created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'free', TRUE, $8, $9, $9)
            """,
            user_id, email, hashed_password, first_name, last_name,
            auth_provider, provider_id, is_verified, now,
        )
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    return dict(row)


def user_to_response(user: dict) -> UserResponse:
    return UserResponse(
        id=str(user["id"]),
        email=user["email"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        auth_provider=user["auth_provider"],
        role=user["role"],
        is_verified=user["is_verified"],
        created_at=user["created_at"].isoformat() if user["created_at"] else "",
    )


def _issue_tokens(user: dict) -> tuple[TokenResponse, str]:
    """Create access + refresh tokens for a user. Returns (TokenResponse, raw_refresh_token)."""
    access_token = create_access_token(
        str(user["id"]), user["email"], user["role"]
    )
    refresh_token = create_refresh_token_value()
    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return token_response, refresh_token


# --- FastAPI Dependencies ---


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Dependency: require a valid access token, return user dict."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    user = await get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled")
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[dict]:
    """Dependency: optionally extract user from token. Returns None if no token."""
    if not credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return await get_user_by_id(payload["sub"])
    except HTTPException:
        return None


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
