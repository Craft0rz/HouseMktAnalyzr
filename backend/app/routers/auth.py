"""Authentication API endpoints: register, login, Google OAuth, token refresh."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    UserResponse,
    _issue_tokens,
    create_access_token,
    create_refresh_token_value,
    get_current_user,
    get_user_by_email,
    create_user,
    hash_password,
    revoke_all_user_tokens,
    store_refresh_token,
    user_to_response,
    validate_and_rotate_refresh_token,
    verify_google_token,
    verify_password,
    TokenResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Request/Response Models ---


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class GoogleAuthRequest(BaseModel):
    id_token: str
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


# --- Helpers ---


def _get_client_info(request: Request) -> tuple[str, str]:
    """Extract user agent and IP from request."""
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""
    return user_agent, ip_address


# --- Endpoints ---


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, request: Request):
    """Register a new user with email and password."""
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    hashed = hash_password(body.password)
    user = await create_user(
        email=body.email,
        hashed_password=hashed,
        first_name=body.first_name,
        last_name=body.last_name,
        auth_provider="local",
        is_verified=False,
    )

    tokens, raw_refresh = _issue_tokens(user)
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(str(user["id"]), raw_refresh, user_agent, ip_address)

    return AuthResponse(user=user_to_response(user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request):
    """Login with email and password."""
    user = await get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user["auth_provider"] != "local":
        raise HTTPException(
            status_code=409,
            detail="This email is linked to Google. Please sign in with Google.",
        )

    if not user["hashed_password"] or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled")

    tokens, raw_refresh = _issue_tokens(user)
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(
        str(user["id"]), raw_refresh, user_agent, ip_address,
        remember_me=body.remember_me,
    )

    return AuthResponse(user=user_to_response(user), tokens=tokens)


@router.post("/google", response_model=AuthResponse)
async def google_auth(body: GoogleAuthRequest, request: Request):
    """Authenticate with Google ID token (login or register)."""
    idinfo = await verify_google_token(body.id_token)

    email = idinfo["email"]
    google_sub = idinfo["sub"]
    given_name = idinfo.get("given_name")
    family_name = idinfo.get("family_name")

    user = await get_user_by_email(email)

    if user:
        if user["auth_provider"] != "google":
            raise HTTPException(
                status_code=409,
                detail="An account with this email exists. Please sign in with your password.",
            )
        if not user["is_active"]:
            raise HTTPException(status_code=403, detail="Account disabled")
    else:
        user = await create_user(
            email=email,
            first_name=given_name,
            last_name=family_name,
            auth_provider="google",
            provider_id=google_sub,
            is_verified=True,
        )

    tokens, raw_refresh = _issue_tokens(user)
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(
        str(user["id"]), raw_refresh, user_agent, ip_address,
        remember_me=body.remember_me,
    )

    return AuthResponse(user=user_to_response(user), tokens=tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request):
    """Refresh access token using refresh token (with rotation)."""
    user_data = await validate_and_rotate_refresh_token(body.refresh_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = create_access_token(
        user_data["user_id"], user_data["email"], user_data["role"]
    )
    new_refresh = create_refresh_token_value()

    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(user_data["user_id"], new_refresh, user_agent, ip_address)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", status_code=204)
async def logout(user: dict = Depends(get_current_user)):
    """Logout: revoke all refresh tokens for this user."""
    await revoke_all_user_tokens(str(user["id"]))


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user profile."""
    return user_to_response(user)
