"""Database connection pool and table management for Postgres."""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None

# Cache TTL defaults
SEARCH_CACHE_TTL_HOURS = 1
DETAIL_CACHE_TTL_HOURS = 24


async def init_pool() -> asyncpg.Pool:
    """Create the connection pool and initialize tables."""
    global _pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    await _create_tables()
    logger.info("Database pool created and tables initialized")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    """Get the current connection pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def _create_tables():
    """Create tables if they don't exist."""
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                city TEXT,
                property_type TEXT,
                price INTEGER,
                data JSONB NOT NULL,
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_properties_expires
            ON properties(expires_at)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_properties_type_price
            ON properties(property_type, price)
        """)
        # Add region column for background scraper (safe to run repeatedly)
        await conn.execute("""
            ALTER TABLE properties ADD COLUMN IF NOT EXISTS region TEXT
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_properties_region_type
            ON properties(region, property_type)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                regions JSONB DEFAULT '[]',
                property_types JSONB DEFAULT '[]',
                min_price INTEGER,
                max_price INTEGER,
                min_score REAL,
                min_cap_rate REAL,
                min_cash_flow INTEGER,
                max_price_per_unit INTEGER,
                min_yield REAL,
                notify_email TEXT,
                notify_on_new BOOLEAN DEFAULT TRUE,
                notify_on_price_drop BOOLEAN DEFAULT TRUE,
                last_checked TIMESTAMPTZ,
                last_match_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Price history for tracking price drops
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                property_id TEXT NOT NULL,
                old_price INTEGER NOT NULL,
                new_price INTEGER NOT NULL,
                recorded_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_history_property
            ON price_history(property_id, recorded_at DESC)
        """)

        # Alert-to-listing match tracking
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_matches (
                alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
                property_id TEXT NOT NULL,
                first_matched_at TIMESTAMPTZ DEFAULT NOW(),
                notified BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (alert_id, property_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id TEXT PRIMARY KEY,
                property_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'watching',
                address TEXT NOT NULL,
                property_type TEXT NOT NULL,
                purchase_price INTEGER,
                purchase_date TEXT,
                down_payment INTEGER,
                mortgage_rate REAL,
                current_rent INTEGER,
                current_expenses INTEGER,
                notes TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


# --- Property cache helpers ---

async def cache_listings(
    listings: list,
    ttl_hours: int = SEARCH_CACHE_TTL_HOURS,
    region: Optional[str] = None,
) -> int:
    """Save listings to the cache.

    Args:
        listings: List of PropertyListing objects (Pydantic models)
        ttl_hours: Cache TTL in hours
        region: Optional region tag for the listings

    Returns:
        Number of listings cached
    """
    if not listings:
        return 0

    pool = get_pool()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=ttl_hours)

    async with pool.acquire() as conn:
        # Fetch current prices to detect changes
        listing_ids = [l.id for l in listings]
        if listing_ids:
            placeholders = ", ".join(f"${i+1}" for i in range(len(listing_ids)))
            existing = await conn.fetch(
                f"SELECT id, price FROM properties WHERE id IN ({placeholders})",
                *listing_ids,
            )
            old_prices = {r["id"]: r["price"] for r in existing}
        else:
            old_prices = {}

        price_changes = 0
        for listing in listings:
            data = json.dumps(listing.model_dump(mode="json"))

            # Record price change if price differs
            old_price = old_prices.get(listing.id)
            if old_price is not None and listing.price and old_price != listing.price:
                await conn.execute(
                    """
                    INSERT INTO price_history (property_id, old_price, new_price, recorded_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    listing.id, old_price, listing.price, now,
                )
                price_changes += 1

            await conn.execute(
                """
                INSERT INTO properties (id, source, city, property_type, price, data, region, fetched_at, expires_at)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    data = EXCLUDED.data,
                    price = EXCLUDED.price,
                    region = COALESCE(EXCLUDED.region, properties.region),
                    fetched_at = EXCLUDED.fetched_at,
                    expires_at = EXCLUDED.expires_at
                """,
                listing.id, listing.source, listing.city,
                listing.property_type.value, listing.price,
                data, region, now, expires,
            )

    if price_changes:
        logger.info(f"Detected {price_changes} price changes")
    logger.info(f"Cached {len(listings)} listings (TTL: {ttl_hours}h)")
    return len(listings)


async def get_cached_listings(
    property_types: Optional[list[str]] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    region: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """Get non-expired cached listings matching filters.

    Returns list of raw dicts (parsed from JSONB data column).
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    conditions = ["expires_at > $1"]
    params: list = [now]
    idx = 2

    if region is not None:
        conditions.append(f"region = ${idx}")
        params.append(region)
        idx += 1

    if property_types:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(property_types)))
        conditions.append(f"property_type IN ({placeholders})")
        params.extend(property_types)
        idx += len(property_types)

    if min_price is not None:
        conditions.append(f"price >= ${idx}")
        params.append(min_price)
        idx += 1

    if max_price is not None:
        conditions.append(f"price <= ${idx}")
        params.append(max_price)
        idx += 1

    where = " AND ".join(conditions)
    query = f"SELECT data FROM properties WHERE {where} ORDER BY price LIMIT ${idx}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [json.loads(row["data"]) for row in rows]


async def get_cached_listing(listing_id: str) -> Optional[dict]:
    """Get a single cached listing by ID (if not expired)."""
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1 AND expires_at > $2",
            listing_id, now,
        )

    if row:
        return json.loads(row["data"])
    return None


async def get_cache_count(property_types: Optional[list[str]] = None) -> int:
    """Count non-expired cached listings, optionally filtered by type."""
    pool = get_pool()
    now = datetime.now(timezone.utc)

    if property_types:
        placeholders = ", ".join(f"${i+2}" for i in range(len(property_types)))
        query = f"SELECT COUNT(*) FROM properties WHERE expires_at > $1 AND property_type IN ({placeholders})"
        params = [now, *property_types]
    else:
        query = "SELECT COUNT(*) FROM properties WHERE expires_at > $1"
        params = [now]

    async with pool.acquire() as conn:
        return await conn.fetchval(query, *params)


async def get_listings_without_walk_score(limit: int = 50) -> list[dict]:
    """Get cached listings that don't have walk scores yet.

    Returns list of dicts with id, address, city, latitude, longitude.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND (data->>'walk_score') IS NULL
            ORDER BY fetched_at DESC
            LIMIT $2
            """,
            now, limit,
        )

    results = []
    for row in rows:
        data = json.loads(row["data"])
        results.append({
            "id": row["id"],
            "address": data.get("address", ""),
            "city": data.get("city", ""),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        })
    return results


async def update_walk_scores(
    listing_id: str,
    walk_score: int | None,
    transit_score: int | None,
    bike_score: int | None,
    latitude: float | None,
    longitude: float | None,
) -> bool:
    """Update walk scores in a listing's JSONB data."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return False

        data = json.loads(row["data"])
        data["walk_score"] = walk_score
        data["transit_score"] = transit_score
        data["bike_score"] = bike_score
        if latitude:
            data["latitude"] = latitude
        if longitude:
            data["longitude"] = longitude

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )
    return True


async def get_scraper_stats() -> dict:
    """Get listing counts grouped by region and property_type."""
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT region, property_type, COUNT(*) as count,
                   MIN(fetched_at) as oldest, MAX(fetched_at) as newest
            FROM properties
            WHERE expires_at > $1
            GROUP BY region, property_type
            ORDER BY region, property_type
            """,
            now,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM properties WHERE expires_at > $1", now
        )
    return {
        "groups": [
            {
                "region": r["region"],
                "property_type": r["property_type"],
                "count": r["count"],
                "oldest": r["oldest"].isoformat() if r["oldest"] else None,
                "newest": r["newest"].isoformat() if r["newest"] else None,
            }
            for r in rows
        ],
        "total": total or 0,
    }
