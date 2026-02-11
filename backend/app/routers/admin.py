"""Admin dashboard endpoints — require admin role."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import get_admin_user
from ..db import get_pool, get_listings_with_bad_coordinates

logger = logging.getLogger(__name__)

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


# --- Removed listings analytics ---


class RemovedListingRow(BaseModel):
    property_id: str
    address: str
    city: str
    region: str | None
    property_type: str | None
    price: int | None
    status: str
    days_on_market: int | None
    last_seen_at: str | None


class RemovedListingsStats(BaseModel):
    total_removed_7d: int
    total_removed_30d: int
    avg_days_on_market: float | None
    by_region: list[dict]
    by_property_type: list[dict]
    weekly_removals: list[dict]


class RemovedListingsResponse(BaseModel):
    stats: RemovedListingsStats
    listings: list[RemovedListingRow]
    total_count: int
    page: int
    page_size: int


@router.get("/removed-listings", response_model=RemovedListingsResponse)
async def get_removed_listings(
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=200),
    region: str | None = Query(default=None),
    _admin: dict = Depends(get_admin_user),
):
    """Removed listings with aggregate analytics (admin only)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        base = "status IN ('stale', 'delisted') AND last_seen_at > NOW() - INTERVAL '30 days'"
        params: list = []
        idx = 1
        if region:
            base += f" AND region = ${idx}"
            params.append(region)
            idx += 1

        total_7d = await conn.fetchval(
            f"SELECT COUNT(*) FROM properties WHERE {base} AND last_seen_at > NOW() - INTERVAL '7 days'",
            *params,
        )
        total_30d = await conn.fetchval(
            f"SELECT COUNT(*) FROM properties WHERE {base}", *params
        )
        avg_dom = await conn.fetchval(
            f"""SELECT AVG(EXTRACT(EPOCH FROM (last_seen_at - first_seen_at)) / 86400)::REAL
                FROM properties WHERE {base} AND first_seen_at IS NOT NULL""",
            *params,
        )

        region_rows = await conn.fetch(
            f"""SELECT region, COUNT(*) AS count FROM properties
                WHERE {base} AND region IS NOT NULL
                GROUP BY region ORDER BY count DESC LIMIT 10""",
            *params,
        )
        type_rows = await conn.fetch(
            f"""SELECT (data->>'property_type') AS property_type, COUNT(*) AS count
                FROM properties WHERE {base}
                GROUP BY property_type ORDER BY count DESC""",
            *params,
        )
        weekly_rows = await conn.fetch(
            f"""SELECT DATE_TRUNC('week', last_seen_at) AS week_start, COUNT(*) AS count
                FROM properties WHERE {base} AND last_seen_at > NOW() - INTERVAL '4 weeks'
                GROUP BY week_start ORDER BY week_start""",
            *params,
        )

        listing_rows = await conn.fetch(
            f"""SELECT id, data, status, region, price, first_seen_at, last_seen_at
                FROM properties WHERE {base}
                ORDER BY last_seen_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}""",
            *params, page_size, page * page_size,
        )

    listings = []
    for row in listing_rows:
        ld = json.loads(row["data"])
        first_seen = row["first_seen_at"]
        last_seen = row["last_seen_at"]
        dom = (last_seen - first_seen).days if first_seen and last_seen else None
        listings.append(RemovedListingRow(
            property_id=row["id"],
            address=ld.get("address", "N/A"),
            city=ld.get("city", "N/A"),
            region=row["region"],
            property_type=ld.get("property_type"),
            price=row["price"] or ld.get("price"),
            status=row["status"],
            days_on_market=dom,
            last_seen_at=last_seen.isoformat() if last_seen else None,
        ))

    return RemovedListingsResponse(
        stats=RemovedListingsStats(
            total_removed_7d=total_7d,
            total_removed_30d=total_30d,
            avg_days_on_market=round(avg_dom, 1) if avg_dom else None,
            by_region=[{"region": r["region"], "count": r["count"]} for r in region_rows],
            by_property_type=[{"property_type": r["property_type"], "count": r["count"]} for r in type_rows],
            weekly_removals=[{"week_start": r["week_start"].isoformat(), "count": r["count"]} for r in weekly_rows],
        ),
        listings=listings,
        total_count=total_30d,
        page=page,
        page_size=page_size,
    )


# --- Geocoding revalidation ---


@router.post("/revalidate-geocoding")
async def revalidate_geocoding(
    _admin: dict = Depends(get_admin_user),
):
    """Re-geocode listings with missing or out-of-Quebec coordinates.

    Finds active listings where lat/lng is null, zero, or outside Quebec
    bounds and re-geocodes them via Nominatim.
    """
    from housemktanalyzr.enrichment.walkscore import geocode_address

    import httpx

    listings = await get_listings_with_bad_coordinates(limit=200)
    if not listings:
        return {"status": "ok", "message": "All listings have valid coordinates", "fixed": 0, "failed": 0}

    fixed = 0
    failed = 0
    headers = {"User-Agent": "HouseMktAnalyzr/1.0"}

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for item in listings:
            try:
                geo = await geocode_address(item["address"], item["city"], client)
                if geo:
                    lat, lon, postal_code = geo
                    # Update only coordinates (preserve existing walk scores)
                    pool = get_pool()
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT data FROM properties WHERE id = $1", item["id"]
                        )
                        if row:
                            data = json.loads(row["data"])
                            data["latitude"] = lat
                            data["longitude"] = lon
                            if postal_code and not data.get("postal_code"):
                                data["postal_code"] = postal_code
                            await conn.execute(
                                "UPDATE properties SET data = $1::jsonb WHERE id = $2",
                                json.dumps(data), item["id"],
                            )
                    fixed += 1
                    logger.info(f"Re-geocoded {item['id']}: ({lat}, {lon})")
                else:
                    failed += 1
                    logger.warning(f"Re-geocoding failed for {item['id']}: {item['address']}, {item['city']}")
            except Exception as e:
                failed += 1
                logger.warning(f"Re-geocoding error for {item['id']}: {e}")

            # Respect Nominatim rate limit (1 req/sec)
            await asyncio.sleep(1.1)

    return {
        "status": "ok",
        "total_checked": len(listings),
        "fixed": fixed,
        "failed": failed,
    }
