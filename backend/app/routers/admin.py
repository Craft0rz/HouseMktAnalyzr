"""Admin dashboard endpoints — require admin role."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import get_admin_user
from ..db import get_pool

router = APIRouter()


# --- Response models ---


class UserRow(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    auth_provider: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: str


class DashboardStats(BaseModel):
    total_users: int
    active_users_24h: int
    total_requests_24h: int
    total_requests_7d: int
    avg_response_ms_24h: int | None
    top_endpoints: list[dict]
    requests_per_day: list[dict]
    users_by_role: list[dict]
    recent_signups: list[UserRow]


# --- Endpoints ---


@router.get("/stats", response_model=DashboardStats)
async def admin_dashboard_stats(_admin: dict = Depends(get_admin_user)):
    """Aggregate statistics for the admin dashboard."""
    pool = get_pool()
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")

        active_24h = await conn.fetchval(
            """SELECT COUNT(DISTINCT user_id) FROM usage_logs
               WHERE user_id IS NOT NULL
                 AND created_at > NOW() - INTERVAL '24 hours'"""
        )

        reqs_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM usage_logs WHERE created_at > NOW() - INTERVAL '24 hours'"
        )
        reqs_7d = await conn.fetchval(
            "SELECT COUNT(*) FROM usage_logs WHERE created_at > NOW() - INTERVAL '7 days'"
        )

        avg_ms = await conn.fetchval(
            "SELECT AVG(response_time_ms)::INTEGER FROM usage_logs WHERE created_at > NOW() - INTERVAL '24 hours'"
        )

        top_rows = await conn.fetch(
            """SELECT endpoint, COUNT(*) AS count
               FROM usage_logs
               WHERE created_at > NOW() - INTERVAL '24 hours'
                 AND endpoint NOT IN ('/health', '/docs', '/redoc', '/openapi.json')
               GROUP BY endpoint ORDER BY count DESC LIMIT 10"""
        )
        top_endpoints = [{"endpoint": r["endpoint"], "count": r["count"]} for r in top_rows]

        rpd_rows = await conn.fetch(
            """SELECT DATE(created_at) AS day, COUNT(*) AS count
               FROM usage_logs
               WHERE created_at > NOW() - INTERVAL '30 days'
               GROUP BY day ORDER BY day"""
        )
        requests_per_day = [{"day": r["day"].isoformat(), "count": r["count"]} for r in rpd_rows]

        role_rows = await conn.fetch(
            "SELECT role, COUNT(*) AS count FROM users GROUP BY role ORDER BY count DESC"
        )
        users_by_role = [{"role": r["role"], "count": r["count"]} for r in role_rows]

        recent_rows = await conn.fetch(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT 10"
        )
        recent_signups = [
            UserRow(
                id=str(r["id"]),
                email=r["email"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                auth_provider=r["auth_provider"],
                role=r["role"],
                is_active=r["is_active"],
                is_verified=r["is_verified"],
                created_at=r["created_at"].isoformat() if r["created_at"] else "",
            )
            for r in recent_rows
        ]

    return DashboardStats(
        total_users=total_users,
        active_users_24h=active_24h,
        total_requests_24h=reqs_24h,
        total_requests_7d=reqs_7d,
        avg_response_ms_24h=avg_ms,
        top_endpoints=top_endpoints,
        requests_per_day=requests_per_day,
        users_by_role=users_by_role,
        recent_signups=recent_signups,
    )


@router.get("/users")
async def list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    _admin: dict = Depends(get_admin_user),
):
    """List all users with pagination."""
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )
    users = [
        {
            "id": str(r["id"]),
            "email": r["email"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "auth_provider": r["auth_provider"],
            "role": r["role"],
            "is_active": r["is_active"],
            "is_verified": r["is_verified"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        }
        for r in rows
    ]
    return {"users": users, "total": total}


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str = Query(..., pattern="^(free|pro|admin)$"),
    _admin: dict = Depends(get_admin_user),
):
    """Change a user's role."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET role = $1, updated_at = $2 WHERE id = $3",
            role, datetime.now(timezone.utc), uuid.UUID(user_id),
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "User not found")
    return {"status": "ok", "user_id": user_id, "role": role}


@router.patch("/users/{user_id}/active")
async def toggle_user_active(
    user_id: str,
    is_active: bool = Query(...),
    _admin: dict = Depends(get_admin_user),
):
    """Enable/disable a user account."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET is_active = $1, updated_at = $2 WHERE id = $3",
            is_active, datetime.now(timezone.utc), uuid.UUID(user_id),
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "User not found")
    return {"status": "ok", "user_id": user_id, "is_active": is_active}
