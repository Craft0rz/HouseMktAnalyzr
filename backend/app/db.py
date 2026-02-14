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
# Real estate listings should persist long-term, not expire quickly
# The scraper will update status to 'stale' or 'delisted' when they disappear
SEARCH_CACHE_TTL_HOURS = 168  # 7 days (was 1 hour - too aggressive)
DETAIL_CACHE_TTL_HOURS = 168  # 7 days (was 24 hours)


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
        # Lifecycle tracking columns
        await conn.execute("""
            ALTER TABLE properties ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ
        """)
        await conn.execute("""
            ALTER TABLE properties ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ
        """)
        await conn.execute("""
            ALTER TABLE properties ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_properties_status
            ON properties(status)
        """)
        # Backfill lifecycle columns for existing rows (idempotent)
        await conn.execute("""
            UPDATE properties
            SET first_seen_at = fetched_at, last_seen_at = fetched_at
            WHERE first_seen_at IS NULL AND fetched_at IS NOT NULL
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
            CREATE TABLE IF NOT EXISTS market_data (
                id SERIAL PRIMARY KEY,
                series_id TEXT NOT NULL,
                date DATE NOT NULL,
                value NUMERIC NOT NULL,
                source TEXT NOT NULL,
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(series_id, date)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_data_series_date
            ON market_data(series_id, date DESC)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS rent_data (
                id SERIAL PRIMARY KEY,
                zone TEXT NOT NULL,
                bedroom_type TEXT NOT NULL,
                year INT NOT NULL,
                avg_rent NUMERIC,
                vacancy_rate NUMERIC,
                universe INT,
                source TEXT DEFAULT 'cmhc',
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(zone, bedroom_type, year)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rent_data_zone_bed
            ON rent_data(zone, bedroom_type, year DESC)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS demographics (
                id SERIAL PRIMARY KEY,
                csd_code TEXT NOT NULL,
                municipality TEXT NOT NULL,
                population INT,
                population_2016 INT,
                pop_change_pct NUMERIC,
                avg_household_size NUMERIC,
                total_households INT,
                median_household_income INT,
                median_after_tax_income INT,
                avg_household_income INT,
                source TEXT DEFAULT 'statcan_2021',
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(csd_code)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS neighbourhood_stats (
                id SERIAL PRIMARY KEY,
                borough TEXT NOT NULL,
                year INT NOT NULL,
                crime_count INT,
                violent_crimes INT,
                property_crimes INT,
                crime_rate_per_1000 NUMERIC,
                crime_change_pct NUMERIC,
                permit_count INT,
                permit_transform_count INT,
                permit_construction_count INT,
                permit_demolition_count INT,
                permit_total_cost NUMERIC,
                housing_starts INT,
                starts_single INT,
                starts_semi INT,
                starts_row INT,
                starts_apartment INT,
                tax_rate_residential NUMERIC,
                tax_rate_total NUMERIC,
                safety_score NUMERIC,
                gentrification_signal TEXT,
                source TEXT DEFAULT 'montreal_open_data',
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(borough, year)
            )
        """)
        # Migrate: add housing starts columns if missing
        for col in ("housing_starts", "starts_single", "starts_semi",
                     "starts_row", "starts_apartment"):
            await conn.execute(f"""
                ALTER TABLE neighbourhood_stats
                ADD COLUMN IF NOT EXISTS {col} INT
            """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tax_rate_history (
                id SERIAL PRIMARY KEY,
                borough TEXT NOT NULL,
                year INT NOT NULL,
                residential_rate NUMERIC,
                total_tax_rate NUMERIC,
                source TEXT DEFAULT 'montreal_open_data',
                fetched_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(borough, year)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tax_rate_history_borough
            ON tax_rate_history(borough, year DESC)
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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_jobs (
                id SERIAL PRIMARY KEY,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'running',
                total_listings INTEGER DEFAULT 0,
                total_enriched INTEGER DEFAULT 0,
                errors JSONB DEFAULT '[]'::jsonb,
                step_log JSONB DEFAULT '[]'::jsonb,
                duration_sec REAL,
                quality_snapshot JSONB DEFAULT NULL
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scrape_jobs_started
            ON scrape_jobs(started_at DESC)
        """)
        # Migrate: add quality_snapshot column if missing
        await conn.execute("""
            ALTER TABLE scrape_jobs
            ADD COLUMN IF NOT EXISTS quality_snapshot JSONB DEFAULT NULL
        """)
        # Mark abandoned running jobs as failed on startup
        await conn.execute("""
            UPDATE scrape_jobs SET status = 'failed', completed_at = NOW()
            WHERE status = 'running' AND started_at < NOW() - INTERVAL '24 hours'
        """)

        # --- Auth tables ---
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT NOT NULL UNIQUE,
                hashed_password TEXT,
                first_name TEXT,
                last_name TEXT,
                auth_provider TEXT NOT NULL DEFAULT 'local',
                provider_id TEXT,
                role TEXT NOT NULL DEFAULT 'free',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_verified BOOLEAN NOT NULL DEFAULT FALSE,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_provider ON users(auth_provider, provider_id)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                replaced_by UUID,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                user_agent TEXT,
                ip_address TEXT
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash)
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER,
                response_time_ms INTEGER,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_logs_user_date ON usage_logs(user_id, created_at DESC)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_logs_date ON usage_logs(created_at DESC)
        """)

        # Add user_id to alerts and portfolio for per-user data
        await conn.execute("""
            ALTER TABLE alerts ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id)
        """)
        await conn.execute("""
            ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_user ON portfolio(user_id)
        """)

        # Promote admin user(s) from env var (no hardcoded emails in source)
        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            await conn.execute("""
                UPDATE users SET role = 'admin'
                WHERE email = $1 AND role != 'admin'
            """, admin_email)


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
                INSERT INTO properties (id, source, city, property_type, price, data, region, fetched_at, expires_at, first_seen_at, last_seen_at, status)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $10, 'active')
                ON CONFLICT (id) DO UPDATE SET
                    data = properties.data || jsonb_strip_nulls(EXCLUDED.data),
                    price = EXCLUDED.price,
                    region = COALESCE(EXCLUDED.region, properties.region),
                    fetched_at = EXCLUDED.fetched_at,
                    expires_at = EXCLUDED.expires_at,
                    last_seen_at = EXCLUDED.last_seen_at,
                    status = 'active'
                """,
                listing.id, listing.source, listing.city,
                listing.property_type.value, listing.price,
                data, region, now, expires, now,
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
    city: Optional[str] = None,
    limit: int = 100,
    include_stale: bool = False,
    new_only: bool = False,
    price_drops_only: bool = False,
) -> list[dict]:
    """Get cached listings matching filters.

    By default returns only active (non-expired) listings.
    With include_stale=True, also returns stale/recently-delisted listings.
    With new_only=True, only returns listings first seen in the last 48 hours.
    With price_drops_only=True, only returns listings with a price drop
    recorded in the last 30 days.

    Returns list of raw dicts (parsed from JSONB data column).
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    if include_stale:
        conditions = [
            "(p.expires_at > $1 OR (p.status IN ('stale', 'delisted') AND p.last_seen_at > $1 - INTERVAL '7 days'))"
        ]
    else:
        conditions = ["p.expires_at > $1"]
    params: list = [now]
    idx = 2

    if region is not None:
        conditions.append(f"p.region = ${idx}")
        params.append(region)
        idx += 1

    if city is not None:
        conditions.append(f"p.city = ${idx}")
        params.append(city)
        idx += 1

    if property_types:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(property_types)))
        conditions.append(f"p.property_type IN ({placeholders})")
        params.extend(property_types)
        idx += len(property_types)

    if min_price is not None:
        conditions.append(f"p.price >= ${idx}")
        params.append(min_price)
        idx += 1

    if max_price is not None:
        conditions.append(f"p.price <= ${idx}")
        params.append(max_price)
        idx += 1

    if new_only:
        conditions.append(f"p.first_seen_at > ${idx}")
        params.append(now - timedelta(hours=48))
        idx += 1

    join_clause = ""
    if price_drops_only:
        join_clause = (
            " INNER JOIN price_history ph ON ph.property_id = p.id"
            f" AND ph.new_price < ph.old_price AND ph.recorded_at > ${idx}"
        )
        params.append(now - timedelta(days=30))
        idx += 1

    where = " AND ".join(conditions)
    limit_clause = f" LIMIT ${idx}" if limit > 0 else ""
    if limit > 0:
        params.append(limit)

    if price_drops_only:
        # JOIN may produce duplicates; DISTINCT needs ORDER BY cols in SELECT
        query = (
            f"SELECT DISTINCT p.data, p.price FROM properties p{join_clause}"
            f" WHERE {where} ORDER BY p.price{limit_clause}"
        )
    else:
        query = (
            f"SELECT p.data FROM properties p"
            f" WHERE {where} ORDER BY p.price{limit_clause}"
        )

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
    Skips listings where walk_score_attempted_at is set (success) or where
    geocoding was attempted within the last 7 days (failure cooldown).
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND (data->>'walk_score') IS NULL
              AND (data->>'walk_score_attempted_at') IS NULL
              AND (
                (data->>'walk_score_failed_at') IS NULL
                OR (data->>'walk_score_failed_at')::timestamptz < ($1 - interval '7 days')
              )
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
    postal_code: str | None = None,
) -> bool:
    """Update walk scores and coordinates in a listing's JSONB data.

    Always stores coordinates and marks the attempt timestamp so the listing
    is not re-queried. Walk scores may be None if scraping failed but
    geocoding succeeded.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return False

        data = json.loads(row["data"])
        if walk_score is not None:
            data["walk_score"] = walk_score
        if transit_score is not None:
            data["transit_score"] = transit_score
        if bike_score is not None:
            data["bike_score"] = bike_score
        if latitude:
            data["latitude"] = latitude
        if longitude:
            data["longitude"] = longitude
        # Only fill postal_code if listing doesn't already have one
        if postal_code and not data.get("postal_code"):
            data["postal_code"] = postal_code
        # Mark as attempted so we don't retry listings where scraping failed
        data["walk_score_attempted_at"] = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )
    return True


async def mark_walk_score_failed(listing_id: str) -> None:
    """Mark a listing's geocoding/walk-score attempt as failed with a timestamp.

    The get_listings_without_walk_score query skips listings where this
    timestamp is less than 7 days old, preventing the same failing addresses
    from consuming the batch budget every cycle.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE properties
            SET data = jsonb_set(data, '{walk_score_failed_at}', to_jsonb($1::text))
            WHERE id = $2
            """,
            datetime.now(timezone.utc).isoformat(),
            listing_id,
        )


async def get_listings_with_bad_coordinates() -> list[dict]:
    """Get active listings with missing or out-of-Quebec coordinates.

    Returns listings where lat/lng is null, zero, or outside Quebec bounds.
    Skips listings already marked with geocode_failed_at (already attempted).
    Quebec bounds: lat 44.0–63.0, lng -80.0–-56.0.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND status = 'active'
              AND (data->>'geocode_failed_at') IS NULL
              AND (
                (data->>'latitude') IS NULL
                OR (data->>'longitude') IS NULL
                OR NOT (
                  (data->>'latitude') ~ E'^-?[0-9]+\\.?[0-9]*$'
                  AND (data->>'longitude') ~ E'^-?[0-9]+\\.?[0-9]*$'
                  AND (data->>'latitude')::float BETWEEN 44.0 AND 63.0
                  AND (data->>'longitude')::float BETWEEN -80.0 AND -56.0
                )
              )
            ORDER BY fetched_at DESC
            """,
            now,
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


async def get_listings_without_photos(limit: int = 30) -> list[dict]:
    """Get cached listings that haven't had photo fetching attempted yet.

    Uses photo_fetch_attempted_at sentinel to prevent infinite retry loops.
    A listing is eligible only if it has never been attempted (no sentinel).
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND (data->>'photo_fetch_attempted_at') IS NULL
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
            "url": data.get("url", ""),
        })
    return results


async def update_photo_urls(listing_id: str, photo_urls: list[str]) -> bool:
    """Update photo_urls in a listing's JSONB data.

    Always sets photo_fetch_attempted_at sentinel to prevent infinite retries.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return False

        data = json.loads(row["data"])
        data["photo_urls"] = photo_urls
        data["photo_fetch_attempted_at"] = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )
    return True


async def get_listings_without_details(limit: int = 50) -> list[dict]:
    """Get cached listings that haven't been validated with detail-page data.

    Returns listings that either:
    - Have never been detail-enriched (no detail_enriched_at marker), OR
    - Are missing critical fields (postal_code, gross_revenue)

    The detail enrichment step validates and auto-corrects ALL fields
    (address, city, units, bedrooms, bathrooms, etc.) using the
    authoritative detail page as the source of truth.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND (data->>'detail_enriched_at') IS NULL
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
            "url": data.get("url", ""),
        })
    return results


async def update_listing_details(
    listing_id: str, detail_fields: dict, column_updates: dict | None = None,
) -> dict:
    """Merge detail-page fields into a cached listing's JSONB data.

    Only updates fields that have a non-None value in detail_fields,
    preserving existing data for fields not present in the update.

    Args:
        listing_id: The property ID.
        detail_fields: Dict of fields to merge into the JSONB data column.
        column_updates: Optional dict of indexed column updates
            (e.g. {"city": "...", "property_type": "..."}).

    Returns:
        Dict with "updated" bool and "corrections" list of changed fields.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return {"updated": False, "corrections": []}

        data = json.loads(row["data"])
        corrections: list[str] = []

        for key, value in detail_fields.items():
            if value is not None:
                old = data.get(key)
                if old is not None and old != value and key != "detail_enriched_at":
                    corrections.append(f"{key}: {old!r} -> {value!r}")
                data[key] = value

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )

        # Also update indexed columns if provided
        if column_updates:
            sets = []
            params = []
            idx = 1
            for col, val in column_updates.items():
                if val is not None:
                    idx += 1
                    sets.append(f"{col} = ${idx}")
                    params.append(val)
            if sets:
                query = f"UPDATE properties SET {', '.join(sets)} WHERE id = $1"
                await conn.execute(query, listing_id, *params)

    return {"updated": True, "corrections": corrections}


async def get_listings_without_condition_score(limit: int = 25) -> list[dict]:
    """Get cached listings that have photos but no condition score.

    Only returns listings where photo_urls exist and condition_score is null.
    Skips listings where condition scoring was attempted in the last 24 hours
    (to avoid hammering Gemini API on persistent failures).
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND (data->>'condition_score') IS NULL
              AND jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
              AND (
                  (data->>'condition_score_attempted_at') IS NULL
                  OR (data->>'condition_score_attempted_at')::timestamptz < $1 - INTERVAL '24 hours'
              )
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
            "photo_urls": data.get("photo_urls", []),
            "property_type": data.get("property_type", "HOUSE"),
            "city": data.get("city", "Montreal"),
            "year_built": data.get("year_built"),
        })
    return results


async def update_condition_score(
    listing_id: str,
    condition_score: float,
    condition_details: dict,
) -> bool:
    """Update condition score in a listing's JSONB data."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return False

        data = json.loads(row["data"])
        data["condition_score"] = condition_score
        data["condition_details"] = condition_details
        data["condition_scored_at"] = datetime.now(timezone.utc).isoformat()

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )
    return True


async def get_houses_without_geo_enrichment(limit: int = 50) -> list[dict]:
    """Get residential listings with coordinates but no geo enrichment data.

    Returns list of dicts with id, latitude, longitude for geo enrichment.
    Includes HOUSE, DUPLEX, TRIPLEX, QUADPLEX, and MULTIPLEX listings where
    latitude/longitude are present and geo_enrichment data is absent or incomplete.

    Uses COALESCE for null-safe JSONB traversal (handles missing raw_data key).
    Also skips listings where geo enrichment was attempted within the last 24 hours
    to avoid hammering external APIs on persistent failures.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, data FROM properties
            WHERE expires_at > $1
              AND property_type IN ('HOUSE', 'DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX')
              AND (data->>'latitude') IS NOT NULL
              AND (data->>'longitude') IS NOT NULL
              AND (
                COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) = 'null'::jsonb
                OR (
                  -- Re-enrich if stored but missing key data (schools + parks both null)
                  (data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m') IS NULL
                  AND COALESCE((data->'raw_data'->'geo_enrichment'->>'park_count_1km')::int, 0) = 0
                  -- But only retry if last attempt was >24h ago
                  AND COALESCE(data->'raw_data'->'geo_enrichment'->>'enriched_at', '2000-01-01')::timestamptz
                      < ($1 - interval '24 hours')
                )
              )
            ORDER BY fetched_at DESC
            LIMIT $2
            """,
            now, limit,
        )

    results = []
    for row in rows:
        data = json.loads(row["data"])
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None and lon is not None:
            results.append({
                "id": row["id"],
                "latitude": float(lat),
                "longitude": float(lon),
                "city": data.get("city"),
                "postal_code": data.get("postal_code"),
            })
    return results


async def update_geo_enrichment(listing_id: str, geo_data: dict) -> bool:
    """Store geo enrichment data in a listing's JSONB data.

    Merges the geo_data dict into the listing's data under the
    'geo_enrichment' key.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data FROM properties WHERE id = $1", listing_id
        )
        if not row:
            return False

        data = json.loads(row["data"])
        # Store inside raw_data so PropertyListing.raw_data preserves it
        # (_fetch_geo_data checks listing.raw_data["geo_enrichment"])
        if not data.get("raw_data"):
            data["raw_data"] = {}
        data["raw_data"]["geo_enrichment"] = geo_data

        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data), listing_id,
        )
    return True


async def upsert_market_data(
    series_id: str,
    observations: list[dict],
    source: str,
) -> int:
    """Upsert time-series observations into market_data table.

    Args:
        series_id: Series identifier (e.g. 'boc_mortgage_5yr')
        observations: List of dicts with 'date' (date) and 'value' (float)
        source: Data source name (e.g. 'bank_of_canada')

    Returns:
        Number of rows upserted
    """
    if not observations:
        return 0

    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        count = 0
        for obs in observations:
            await conn.execute(
                """
                INSERT INTO market_data (series_id, date, value, source, fetched_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (series_id, date) DO UPDATE SET
                    value = EXCLUDED.value,
                    fetched_at = EXCLUDED.fetched_at
                """,
                series_id, obs["date"], float(obs["value"]), source, now,
            )
            count += 1

    return count


async def get_market_series(
    series_id: str,
    start_date=None,
    end_date=None,
    limit: int = 500,
) -> list[dict]:
    """Query market_data for a series, ordered by date descending.

    Returns list of dicts with 'date' and 'value' keys.
    """
    pool = get_pool()

    conditions = ["series_id = $1"]
    params: list = [series_id]
    idx = 2

    if start_date is not None:
        conditions.append(f"date >= ${idx}")
        params.append(start_date)
        idx += 1

    if end_date is not None:
        conditions.append(f"date <= ${idx}")
        params.append(end_date)
        idx += 1

    where = " AND ".join(conditions)
    query = f"""
        SELECT date, value FROM market_data
        WHERE {where}
        ORDER BY date DESC
        LIMIT ${idx}
    """
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [
        {"date": row["date"].isoformat(), "value": float(row["value"])}
        for row in rows
    ]


async def get_latest_market_value(series_id: str) -> Optional[dict]:
    """Get the most recent value for a market data series."""
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT date, value, fetched_at FROM market_data
            WHERE series_id = $1
            ORDER BY date DESC
            LIMIT 1
            """,
            series_id,
        )

    if row:
        return {
            "date": row["date"].isoformat(),
            "value": float(row["value"]),
            "fetched_at": row["fetched_at"].isoformat() if row["fetched_at"] else None,
        }
    return None


async def get_market_data_age(series_id: str) -> Optional[float]:
    """Get the age in hours of the most recent fetch for a series.

    Returns None if no data exists.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest FROM market_data WHERE series_id = $1",
            series_id,
        )

    if row and row["latest"]:
        age = datetime.now(timezone.utc) - row["latest"]
        return age.total_seconds() / 3600
    return None


# --- Rent data helpers ---

async def upsert_rent_data(
    zone: str,
    bedroom_type: str,
    year: int,
    avg_rent: float | None = None,
    vacancy_rate: float | None = None,
    universe: int | None = None,
    source: str = "cmhc",
) -> bool:
    """Upsert a single rent data point. Returns True if inserted/updated."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rent_data (zone, bedroom_type, year, avg_rent, vacancy_rate, universe, source, fetched_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (zone, bedroom_type, year)
            DO UPDATE SET avg_rent = COALESCE($4, rent_data.avg_rent),
                         vacancy_rate = COALESCE($5, rent_data.vacancy_rate),
                         universe = COALESCE($6, rent_data.universe),
                         fetched_at = NOW()
            """,
            zone, bedroom_type, year, avg_rent, vacancy_rate, universe, source,
        )
    return True


async def upsert_rent_data_batch(rows: list[dict], source: str = "cmhc") -> int:
    """Bulk upsert rent data rows. Each row needs zone, bedroom_type, year, and optional avg_rent/vacancy_rate."""
    pool = get_pool()
    count = 0
    async with pool.acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO rent_data (zone, bedroom_type, year, avg_rent, vacancy_rate, universe, source, fetched_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (zone, bedroom_type, year)
                DO UPDATE SET avg_rent = COALESCE($4, rent_data.avg_rent),
                             vacancy_rate = COALESCE($5, rent_data.vacancy_rate),
                             universe = COALESCE($6, rent_data.universe),
                             fetched_at = NOW()
                """,
                row["zone"], row["bedroom_type"], row["year"],
                row.get("avg_rent"), row.get("vacancy_rate"),
                row.get("universe"), source,
            )
            count += 1
    return count


async def get_rent_history(
    zone: str, bedroom_type: str, limit: int = 20
) -> list[dict]:
    """Get historical rent data for a zone and bedroom type."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT year, avg_rent, vacancy_rate, universe
            FROM rent_data
            WHERE zone = $1 AND bedroom_type = $2
            ORDER BY year DESC
            LIMIT $3
            """,
            zone, bedroom_type, limit,
        )
    return [dict(r) for r in rows]


async def get_rent_history_fuzzy(
    zone_candidates: list[str], bedroom_type: str, limit: int = 20
) -> list[dict]:
    """Get rent data trying zone candidates in order (best match first).

    For each candidate, tries exact match then partial (LIKE) match.
    Falls back through the list until data is found.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        for candidate in zone_candidates:
            # Exact match
            rows = await conn.fetch(
                """
                SELECT year, avg_rent, vacancy_rate, universe
                FROM rent_data
                WHERE zone = $1 AND bedroom_type = $2
                ORDER BY year DESC
                LIMIT $3
                """,
                candidate, bedroom_type, limit,
            )
            if rows:
                return [dict(r) for r in rows]

            # Partial match: CMHC zones often contain borough name
            # e.g. "Zone 5 / Le Plateau-Mont-Royal" matches "Le Plateau-Mont-Royal"
            rows = await conn.fetch(
                """
                SELECT year, avg_rent, vacancy_rate, universe
                FROM rent_data
                WHERE LOWER(zone) LIKE '%' || LOWER($1) || '%'
                  AND bedroom_type = $2
                ORDER BY year DESC
                LIMIT $3
                """,
                candidate, bedroom_type, limit,
            )
            if rows:
                return [dict(r) for r in rows]

    return []


async def get_rent_zones() -> list[str]:
    """Get all available CMHC zones with rent data."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT zone FROM rent_data ORDER BY zone"
        )
    return [r["zone"] for r in rows]


async def get_latest_rent(zone: str, bedroom_type: str) -> dict | None:
    """Get the most recent rent data for a zone/bedroom combo."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT year, avg_rent, vacancy_rate, universe
            FROM rent_data
            WHERE zone = $1 AND bedroom_type = $2
            ORDER BY year DESC
            LIMIT 1
            """,
            zone, bedroom_type,
        )
    return dict(row) if row else None


async def get_rent_data_age() -> Optional[float]:
    """Get age in hours of the most recent rent data fetch."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest FROM rent_data"
        )
    if row and row["latest"]:
        age = datetime.now(timezone.utc) - row["latest"]
        return age.total_seconds() / 3600
    return None


# --- Demographics helpers ---

async def upsert_demographics(profile: dict) -> bool:
    """Upsert a demographics profile by CSD code. Returns True on success."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO demographics (
                csd_code, municipality, population, population_2016,
                pop_change_pct, avg_household_size, total_households,
                median_household_income, median_after_tax_income,
                avg_household_income, source, fetched_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            ON CONFLICT (csd_code) DO UPDATE SET
                municipality = EXCLUDED.municipality,
                population = COALESCE(EXCLUDED.population, demographics.population),
                population_2016 = COALESCE(EXCLUDED.population_2016, demographics.population_2016),
                pop_change_pct = COALESCE(EXCLUDED.pop_change_pct, demographics.pop_change_pct),
                avg_household_size = COALESCE(EXCLUDED.avg_household_size, demographics.avg_household_size),
                total_households = COALESCE(EXCLUDED.total_households, demographics.total_households),
                median_household_income = COALESCE(EXCLUDED.median_household_income, demographics.median_household_income),
                median_after_tax_income = COALESCE(EXCLUDED.median_after_tax_income, demographics.median_after_tax_income),
                avg_household_income = COALESCE(EXCLUDED.avg_household_income, demographics.avg_household_income),
                fetched_at = NOW()
            """,
            profile["csd_code"], profile["municipality"],
            profile.get("population"), profile.get("population_2016"),
            profile.get("pop_change_pct"), profile.get("avg_household_size"),
            profile.get("total_households"), profile.get("median_household_income"),
            profile.get("median_after_tax_income"), profile.get("avg_household_income"),
            profile.get("source", "statcan_2021"),
        )
    return True


async def upsert_demographics_batch(profiles: list[dict]) -> int:
    """Bulk upsert demographics profiles. Returns count upserted."""
    count = 0
    for profile in profiles:
        await upsert_demographics(profile)
        count += 1
    return count


async def get_demographics_for_city(city: str) -> Optional[dict]:
    """Look up demographics by municipality name (case-insensitive partial match)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Try exact match first
        row = await conn.fetchrow(
            "SELECT * FROM demographics WHERE LOWER(municipality) = LOWER($1)",
            city,
        )
        if not row:
            # Partial match
            row = await conn.fetchrow(
                "SELECT * FROM demographics WHERE LOWER(municipality) LIKE '%' || LOWER($1) || '%'",
                city,
            )
    return dict(row) if row else None


async def get_demographics_by_csd(csd_code: str) -> Optional[dict]:
    """Get demographics by CSD code."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM demographics WHERE csd_code = $1",
            csd_code,
        )
    return dict(row) if row else None


async def get_all_demographics() -> list[dict]:
    """Get all cached demographics profiles."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM demographics ORDER BY municipality"
        )
    return [dict(r) for r in rows]


async def get_demographics_age() -> Optional[float]:
    """Get age in hours of the most recent demographics fetch."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest FROM demographics"
        )
    if row and row["latest"]:
        age = datetime.now(timezone.utc) - row["latest"]
        return age.total_seconds() / 3600
    return None


# --- Neighbourhood stats helpers ---

async def upsert_neighbourhood_stats(stats: dict) -> bool:
    """Upsert neighbourhood stats by borough + year. Returns True on success."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO neighbourhood_stats (
                borough, year, crime_count, violent_crimes, property_crimes,
                crime_rate_per_1000, crime_change_pct,
                permit_count, permit_transform_count, permit_construction_count,
                permit_demolition_count, permit_total_cost,
                housing_starts, starts_single, starts_semi, starts_row, starts_apartment,
                tax_rate_residential, tax_rate_total,
                safety_score, gentrification_signal, source, fetched_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22, NOW())
            ON CONFLICT (borough, year) DO UPDATE SET
                crime_count = COALESCE($3, neighbourhood_stats.crime_count),
                violent_crimes = COALESCE($4, neighbourhood_stats.violent_crimes),
                property_crimes = COALESCE($5, neighbourhood_stats.property_crimes),
                crime_rate_per_1000 = COALESCE($6, neighbourhood_stats.crime_rate_per_1000),
                crime_change_pct = COALESCE($7, neighbourhood_stats.crime_change_pct),
                permit_count = COALESCE($8, neighbourhood_stats.permit_count),
                permit_transform_count = COALESCE($9, neighbourhood_stats.permit_transform_count),
                permit_construction_count = COALESCE($10, neighbourhood_stats.permit_construction_count),
                permit_demolition_count = COALESCE($11, neighbourhood_stats.permit_demolition_count),
                permit_total_cost = COALESCE($12, neighbourhood_stats.permit_total_cost),
                housing_starts = COALESCE($13, neighbourhood_stats.housing_starts),
                starts_single = COALESCE($14, neighbourhood_stats.starts_single),
                starts_semi = COALESCE($15, neighbourhood_stats.starts_semi),
                starts_row = COALESCE($16, neighbourhood_stats.starts_row),
                starts_apartment = COALESCE($17, neighbourhood_stats.starts_apartment),
                tax_rate_residential = COALESCE($18, neighbourhood_stats.tax_rate_residential),
                tax_rate_total = COALESCE($19, neighbourhood_stats.tax_rate_total),
                safety_score = COALESCE($20, neighbourhood_stats.safety_score),
                gentrification_signal = COALESCE($21, neighbourhood_stats.gentrification_signal),
                fetched_at = NOW()
            """,
            stats["borough"], stats["year"],
            stats.get("crime_count"), stats.get("violent_crimes"),
            stats.get("property_crimes"), stats.get("crime_rate_per_1000"),
            stats.get("crime_change_pct"),
            stats.get("permit_count"), stats.get("permit_transform_count"),
            stats.get("permit_construction_count"), stats.get("permit_demolition_count"),
            stats.get("permit_total_cost"),
            stats.get("housing_starts"), stats.get("starts_single"),
            stats.get("starts_semi"), stats.get("starts_row"),
            stats.get("starts_apartment"),
            stats.get("tax_rate_residential"), stats.get("tax_rate_total"),
            stats.get("safety_score"), stats.get("gentrification_signal"),
            stats.get("source", "montreal_open_data"),
        )
    return True


async def upsert_neighbourhood_stats_batch(rows: list[dict]) -> int:
    """Bulk upsert neighbourhood stats. Returns count upserted."""
    count = 0
    for row in rows:
        await upsert_neighbourhood_stats(row)
        count += 1
    return count


async def get_neighbourhood_stats_for_borough(borough: str) -> Optional[dict]:
    """Get the most recent neighbourhood stats for a borough (case-insensitive)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM neighbourhood_stats
            WHERE LOWER(borough) = LOWER($1)
            ORDER BY year DESC
            LIMIT 1
            """,
            borough,
        )
    return dict(row) if row else None


async def get_all_neighbourhood_stats(year: int | None = None) -> list[dict]:
    """Get all neighbourhood stats, optionally filtered by year."""
    pool = get_pool()
    async with pool.acquire() as conn:
        if year:
            rows = await conn.fetch(
                "SELECT * FROM neighbourhood_stats WHERE year = $1 ORDER BY borough",
                year,
            )
        else:
            # Get most recent year for each borough
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (borough) *
                FROM neighbourhood_stats
                ORDER BY borough, year DESC
                """
            )
    return [dict(r) for r in rows]


async def get_neighbourhood_stats_age() -> Optional[float]:
    """Get age in hours of the most recent neighbourhood stats fetch."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest FROM neighbourhood_stats"
        )
    if row and row["latest"]:
        age = datetime.now(timezone.utc) - row["latest"]
        return age.total_seconds() / 3600
    return None


async def upsert_tax_rate_history_batch(rows: list[dict]) -> int:
    """Bulk upsert tax rate history rows. Each row needs borough, year, residential_rate, total_tax_rate."""
    pool = get_pool()
    count = 0
    async with pool.acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO tax_rate_history (borough, year, residential_rate, total_tax_rate, source, fetched_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (borough, year) DO UPDATE SET
                    residential_rate = COALESCE(EXCLUDED.residential_rate, tax_rate_history.residential_rate),
                    total_tax_rate = COALESCE(EXCLUDED.total_tax_rate, tax_rate_history.total_tax_rate),
                    fetched_at = NOW()
                """,
                row["borough"], row["year"],
                row.get("residential_rate"), row.get("total_tax_rate"),
                row.get("source", "montreal_open_data"),
            )
            count += 1
    return count


async def get_tax_history_for_borough(borough: str, years: int = 5) -> list[dict]:
    """Get tax rate history for a borough (case-insensitive), most recent first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT year, residential_rate, total_tax_rate
            FROM tax_rate_history
            WHERE LOWER(borough) = LOWER($1)
            ORDER BY year DESC
            LIMIT $2
            """,
            borough, years,
        )
        if not rows:
            # Partial match
            rows = await conn.fetch(
                """
                SELECT year, residential_rate, total_tax_rate
                FROM tax_rate_history
                WHERE LOWER(borough) LIKE '%' || LOWER($1) || '%'
                ORDER BY year DESC
                LIMIT $2
                """,
                borough, years,
            )
    return [
        {
            "year": r["year"],
            "residential_rate": float(r["residential_rate"]) if r["residential_rate"] else None,
            "total_tax_rate": float(r["total_tax_rate"]) if r["total_tax_rate"] else None,
        }
        for r in rows
    ]


async def get_all_boroughs_latest_tax_rate() -> list[dict]:
    """Get the latest tax rate for all boroughs (for ranking/comparison)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (borough) borough, year, residential_rate, total_tax_rate
            FROM tax_rate_history
            ORDER BY borough, year DESC
            """
        )
    return [
        {
            "borough": r["borough"],
            "year": r["year"],
            "residential_rate": float(r["residential_rate"]) if r["residential_rate"] else None,
            "total_tax_rate": float(r["total_tax_rate"]) if r["total_tax_rate"] else None,
        }
        for r in rows
    ]


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


# --- Listing lifecycle helpers ---

async def get_price_history(property_id: str) -> list[dict]:
    """Get all price changes for a listing, newest first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT old_price, new_price, recorded_at
            FROM price_history
            WHERE property_id = $1
            ORDER BY recorded_at DESC
            """,
            property_id,
        )
    return [
        {
            "old_price": r["old_price"],
            "new_price": r["new_price"],
            "change": r["new_price"] - r["old_price"],
            "change_pct": round(
                (r["new_price"] - r["old_price"]) / r["old_price"] * 100, 1
            ) if r["old_price"] else 0,
            "recorded_at": r["recorded_at"].isoformat(),
        }
        for r in rows
    ]


async def get_listing_lifecycle(property_id: str) -> Optional[dict]:
    """Get lifecycle metadata for a listing (first_seen, last_seen, status, DOM)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT first_seen_at, last_seen_at, status, price
            FROM properties WHERE id = $1
            """,
            property_id,
        )
    if not row:
        return None

    first_seen = row["first_seen_at"]
    last_seen = row["last_seen_at"]
    now = datetime.now(timezone.utc)

    days_on_market = None
    if first_seen:
        days_on_market = (now - first_seen).days

    return {
        "first_seen_at": first_seen.isoformat() if first_seen else None,
        "last_seen_at": last_seen.isoformat() if last_seen else None,
        "status": row["status"] or "active",
        "days_on_market": days_on_market,
        "current_price": row["price"],
    }


async def get_batch_lifecycle() -> list[dict]:
    """Get lifecycle metadata for all non-delisted listings.

    Returns list of dicts with id, status, first_seen_at, days_on_market.
    Used by frontend to render status badges and DOM column.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, first_seen_at, last_seen_at, status
            FROM properties
            WHERE status IN ('active', 'stale')
              OR (status = 'delisted' AND last_seen_at > NOW() - INTERVAL '7 days')
            """
        )
    results = []
    for r in rows:
        first_seen = r["first_seen_at"]
        days_on_market = (now - first_seen).days if first_seen else None
        results.append({
            "id": r["id"],
            "status": r["status"] or "active",
            "first_seen_at": first_seen.isoformat() if first_seen else None,
            "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
            "days_on_market": days_on_market,
        })
    return results


async def get_recent_price_changes(limit: int = 100) -> list[dict]:
    """Get listings with recent price changes (for badge display).

    Returns property_id, latest old_price, new_price, change, change_pct,
    and recorded_at for listings that had a price change in the last 30 days.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (ph.property_id)
                ph.property_id, ph.old_price, ph.new_price, ph.recorded_at
            FROM price_history ph
            JOIN properties p ON p.id = ph.property_id
            WHERE ph.recorded_at > NOW() - INTERVAL '30 days'
              AND p.status = 'active'
            ORDER BY ph.property_id, ph.recorded_at DESC
            """,
        )
    return [
        {
            "property_id": r["property_id"],
            "old_price": r["old_price"],
            "new_price": r["new_price"],
            "change": r["new_price"] - r["old_price"],
            "change_pct": round(
                (r["new_price"] - r["old_price"]) / r["old_price"] * 100, 1
            ) if r["old_price"] else 0,
            "recorded_at": r["recorded_at"].isoformat(),
        }
        for r in rows
    ]


async def mark_stale_listings(ttl_hours: int = 6) -> int:
    """Mark listings as 'stale' if they haven't been seen in 2+ scrape cycles.

    A listing is stale if its last_seen_at is older than 2x the TTL.
    Returns count of newly stale listings.
    """
    pool = get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours * 2)

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE properties SET status = 'stale'
            WHERE status = 'active'
              AND last_seen_at IS NOT NULL
              AND last_seen_at < $1
            """,
            cutoff,
        )
    # asyncpg returns "UPDATE N"
    count = int(result.split()[-1])
    if count:
        logger.info(f"Marked {count} listings as stale (not seen since {cutoff.isoformat()})")
    return count


async def mark_delisted(hours: int = 48) -> int:
    """Mark stale listings as 'delisted' if not seen for 48+ hours.

    Returns count of newly delisted listings.
    """
    pool = get_pool()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE properties SET status = 'delisted'
            WHERE status = 'stale'
              AND last_seen_at IS NOT NULL
              AND last_seen_at < $1
            """,
            cutoff,
        )
    count = int(result.split()[-1])
    if count:
        logger.info(f"Marked {count} listings as delisted (not seen for {hours}+ hours)")
    return count


# --- Scrape job history helpers ---

async def insert_scrape_job(
    started_at: datetime,
    completed_at: datetime | None,
    status: str,
    total_listings: int,
    total_enriched: int,
    errors: list[str],
    step_log: list[dict],
    duration_sec: float | None,
    quality_snapshot: dict | None = None,
) -> int:
    """Insert a scrape job record and return its ID."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scrape_jobs
                (started_at, completed_at, status, total_listings,
                 total_enriched, errors, step_log, duration_sec,
                 quality_snapshot)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9::jsonb)
            RETURNING id
            """,
            started_at,
            completed_at,
            status,
            total_listings,
            total_enriched,
            json.dumps(errors),
            json.dumps(step_log),
            duration_sec,
            json.dumps(quality_snapshot) if quality_snapshot else None,
        )
    return row["id"]


async def get_scrape_job_history(limit: int = 20) -> list[dict]:
    """Get the most recent scrape jobs, newest first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, started_at, completed_at, status,
                   total_listings, total_enriched, errors,
                   step_log, duration_sec, quality_snapshot
            FROM scrape_jobs
            ORDER BY started_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [
        {
            "id": r["id"],
            "started_at": r["started_at"].isoformat() if r["started_at"] else None,
            "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
            "status": r["status"],
            "total_listings": r["total_listings"],
            "total_enriched": r["total_enriched"],
            "errors": json.loads(r["errors"]) if r["errors"] else [],
            "step_log": json.loads(r["step_log"]) if r["step_log"] else [],
            "duration_sec": r["duration_sec"],
            "quality_snapshot": json.loads(r["quality_snapshot"]) if r["quality_snapshot"] else None,
        }
        for r in rows
    ]


async def get_data_freshness() -> dict:
    """Get freshness (age in hours + last fetched timestamp) for all data sources.

    Includes severity indicators:
    - ok: within threshold
    - warning: 1.5x-2x threshold (stale but not critical)
    - critical: >2x threshold (urgent action needed)
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    result = {}

    def _assess_freshness(age_hours: float | None, threshold: int, name: str) -> dict:
        """Add severity and action message based on freshness."""
        base = {
            "last_fetched": None,
            "age_hours": age_hours,
            "threshold_hours": threshold,
        }

        if age_hours is None:
            return {
                **base,
                "status": "critical",
                "action": f"CRITICAL: {name} has never been fetched - immediate action required",
            }

        if age_hours <= threshold:
            return {
                **base,
                "status": "ok",
                "action": None,
            }
        elif age_hours <= threshold * 1.5:
            return {
                **base,
                "status": "warning",
                "action": f"WARNING: {name} is getting stale ({age_hours:.0f}h old, refresh in {threshold * 1.5 - age_hours:.0f}h)",
            }
        elif age_hours <= threshold * 2:
            return {
                **base,
                "status": "warning",
                "action": f"WARNING: {name} is stale ({age_hours:.0f}h old, expected every {threshold}h)",
            }
        else:
            missed_cycles = int(age_hours / threshold) - 1
            return {
                **base,
                "status": "critical",
                "action": f"CRITICAL: {name} hasn't updated in {age_hours:.0f}h ({missed_cycles} missed cycles) - check scraper",
            }

    async with pool.acquire() as conn:
        # Market data
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest FROM market_data WHERE series_id = 'boc_mortgage_5yr'"
        )
        age = ((now - row["latest"]).total_seconds() / 3600) if row and row["latest"] else None
        result["market_data"] = _assess_freshness(age, 24, "Market data")
        if row and row["latest"]:
            result["market_data"]["last_fetched"] = row["latest"].isoformat()

        # Rent data
        row = await conn.fetchrow("SELECT MAX(fetched_at) as latest FROM rent_data")
        age = ((now - row["latest"]).total_seconds() / 3600) if row and row["latest"] else None
        result["rent_data"] = _assess_freshness(age, 168, "Rent data")
        if row and row["latest"]:
            result["rent_data"]["last_fetched"] = row["latest"].isoformat()

        # Demographics
        row = await conn.fetchrow("SELECT MAX(fetched_at) as latest FROM demographics")
        age = ((now - row["latest"]).total_seconds() / 3600) if row and row["latest"] else None
        result["demographics"] = _assess_freshness(age, 720, "Demographics")
        if row and row["latest"]:
            result["demographics"]["last_fetched"] = row["latest"].isoformat()

        # Neighbourhood stats
        row = await conn.fetchrow("SELECT MAX(fetched_at) as latest FROM neighbourhood_stats")
        age = ((now - row["latest"]).total_seconds() / 3600) if row and row["latest"] else None
        result["neighbourhood"] = _assess_freshness(age, 168, "Neighbourhood")
        if row and row["latest"]:
            result["neighbourhood"]["last_fetched"] = row["latest"].isoformat()

        # Listings
        row = await conn.fetchrow(
            "SELECT MAX(fetched_at) as latest, COUNT(*) as total FROM properties WHERE status = 'active'"
        )
        age = ((now - row["latest"]).total_seconds() / 3600) if row and row["latest"] else None
        result["listings"] = _assess_freshness(age, 4, "Listings")
        if row and row["latest"]:
            result["listings"]["last_fetched"] = row["latest"].isoformat()
            result["listings"]["total_active"] = row["total"]
        else:
            result["listings"]["total_active"] = 0

    return result


async def get_data_quality_summary() -> dict:
    """Get aggregate data quality stats across all active listings, with per-type breakdown."""
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                property_type,
                COUNT(*) as total,
                COALESCE(AVG((data->'_quality'->>'score')::int), 0) as avg_score,
                COUNT(*) FILTER (
                    WHERE (data->'_quality'->>'score')::int >= 80
                ) as high_quality,
                COUNT(*) FILTER (
                    WHERE (data->'_quality'->>'score')::int < 50
                ) as low_quality,
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'_quality'->'flags', '[]'::jsonb)) > 0
                ) as flagged,
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'_quality'->'corrections', '[]'::jsonb)) > 0
                ) as corrected
            FROM properties
            WHERE expires_at > $1
              AND data->'_quality' IS NOT NULL
            GROUP BY property_type
            """,
            now,
        )

    if not rows:
        return {}

    def _row_to_dict(r) -> dict:
        return {
            "total": r["total"],
            "avg_score": round(float(r["avg_score"]), 1),
            "high_quality": r["high_quality"],
            "low_quality": r["low_quality"],
            "flagged": r["flagged"],
            "corrected": r["corrected"],
        }

    # Per-type breakdown
    by_type = {}
    for r in rows:
        by_type[r["property_type"]] = _row_to_dict(r)

    # Compute aggregate totals
    total = sum(r["total"] for r in rows)
    avg_score = sum(r["total"] * float(r["avg_score"]) for r in rows) / total if total else 0
    result = {
        "total": total,
        "avg_score": round(avg_score, 1),
        "high_quality": sum(r["high_quality"] for r in rows),
        "low_quality": sum(r["low_quality"] for r in rows),
        "flagged": sum(r["flagged"] for r in rows),
        "corrected": sum(r["corrected"] for r in rows),
        "by_type": by_type,
    }
    return result


async def get_geo_enrichment_stats() -> dict:
    """Get geo enrichment statistics for residential listings.

    Returns counts of total residential (houses + plexes), enriched, pending,
    incomplete, and recently failed.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)
    geo_types = ('HOUSE', 'DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX')

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                ) as total_houses,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND (data->>'longitude') IS NOT NULL
                ) as with_coords,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                ) as enriched,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                      AND (data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m') IS NOT NULL
                ) as has_schools,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                      AND COALESCE((data->'raw_data'->'geo_enrichment'->>'park_count_1km')::int, 0) > 0
                ) as has_parks,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                      AND (data->'raw_data'->'geo_enrichment'->>'flood_zone') IS NOT NULL
                ) as has_flood,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                      AND (data->'raw_data'->'geo_enrichment'->>'nearest_elementary_m') IS NULL
                      AND COALESCE((data->'raw_data'->'geo_enrichment'->>'park_count_1km')::int, 0) = 0
                ) as incomplete,
                COUNT(*) FILTER (
                    WHERE property_type = ANY($2)
                      AND (data->>'latitude') IS NULL
                      AND (data->>'walk_score_failed_at') IS NOT NULL
                ) as geocoding_failed
            FROM properties
            WHERE expires_at > $1
            """,
            now, list(geo_types),
        )

    total = row["total_houses"]
    enriched = row["enriched"]
    with_coords = row["with_coords"]
    pending = with_coords - enriched
    no_coords = total - with_coords
    success_rate = round(enriched / with_coords * 100, 1) if with_coords > 0 else 0

    # Assess severity based on success rate
    if success_rate >= 90:
        status = "ok"
        action = None
    elif success_rate >= 70:
        status = "warning"
        action = f"WARNING: Geo enrichment: {pending:,} residential pending ({success_rate}% coverage)"
    elif success_rate >= 30:
        status = "warning"
        action = f"WARNING: Geo enrichment backlog: {pending:,} of {with_coords:,} residential need enrichment ({success_rate}% coverage)"
    else:
        status = "critical"
        action = f"CRITICAL: Geo enrichment severely behind - only {enriched:,} of {with_coords:,} enriched ({success_rate}% coverage)"

    return {
        "total_houses": total,
        "with_coords": with_coords,
        "no_coords": no_coords,
        "geocoding_failed": row["geocoding_failed"],
        "enriched": enriched,
        "pending": max(0, pending),
        "incomplete": row["incomplete"],
        "has_schools": row["has_schools"],
        "has_parks": row["has_parks"],
        "has_flood": row["has_flood"],
        "success_rate": success_rate,
        "status": status,
        "action": action,
    }


async def get_enrichment_backlog() -> dict:
    """Get per-datapoint enrichment backlog counts across all active listings.

    Returns counts of how many listings have vs. are missing each enrichment
    data point, enabling the status dashboard to show exact coverage.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (
                    WHERE (data->>'latitude') IS NOT NULL
                      AND (data->>'longitude') IS NOT NULL
                      AND (data->>'latitude') != '0'
                      AND (data->>'longitude') != '0'
                ) as has_coords,
                COUNT(*) FILTER (
                    WHERE (data->>'walk_score') IS NOT NULL
                ) as has_walk_score,
                COUNT(*) FILTER (
                    WHERE (data->>'detail_enriched_at') IS NOT NULL
                ) as has_details,
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
                ) as has_photos,
                COUNT(*) FILTER (
                    WHERE (data->>'condition_score') IS NOT NULL
                ) as has_condition,
                COUNT(*) FILTER (
                    WHERE property_type IN ('HOUSE', 'DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX')
                ) as total_houses,
                COUNT(*) FILTER (
                    WHERE property_type IN ('HOUSE', 'DUPLEX', 'TRIPLEX', 'QUADPLEX', 'MULTIPLEX')
                      AND (data->>'latitude') IS NOT NULL
                      AND data->'raw_data'->'geo_enrichment' IS NOT NULL
                      AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
                ) as has_geo
            FROM properties
            WHERE expires_at > $1 AND status = 'active'
            """,
            now,
        )

    total = row["total"]

    def _item(label: str, done: int, of: int, note: str = "") -> dict:
        coverage = round(done / of * 100, 1) if of > 0 else 0
        missing = of - done

        # Determine severity based on coverage percentage
        if coverage >= 90:
            status = "ok"
            action = None
        elif coverage >= 70:
            status = "warning"
            action = f"WARNING: {label}: {missing:,} items pending ({coverage}% coverage)"
        elif coverage >= 50:
            status = "warning"
            action = f"WARNING: {label}: Large backlog - {missing:,} items need enrichment ({coverage}% coverage)"
        else:
            status = "critical"
            action = f"CRITICAL: {label} severely behind - {missing:,} of {of:,} missing ({coverage}% coverage)"

        return {
            "label": label,
            "done": done,
            "missing": missing,
            "total": of,
            "coverage": coverage,
            "status": status,
            "action": action,
            "note": note,
        }

    return {
        "total": total,
        "datapoints": [
            _item("Coordinates", row["has_coords"], total),
            _item("Detail Enrichment", row["has_details"], total),
            _item("Walk Score", row["has_walk_score"], total),
            _item("Photos", row["has_photos"], total),
            _item("Condition Score", row["has_condition"], total),
            _item("Geo Enrichment", row["has_geo"], row["total_houses"], "Residential"),
        ],
    }


async def get_batch_price_drops(property_ids: list[str]) -> dict[str, list[dict]]:
    """Get price history for multiple listings in a single query.

    Returns a dict mapping property_id → list of price change dicts.
    Only includes listings that had at least one price change.
    """
    if not property_ids:
        return {}

    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT property_id, old_price, new_price, recorded_at
            FROM price_history
            WHERE property_id = ANY($1::text[])
            ORDER BY property_id, recorded_at DESC
            """,
            property_ids,
        )

    result: dict[str, list[dict]] = {}
    for r in rows:
        pid = r["property_id"]
        if pid not in result:
            result[pid] = []
        result[pid].append({
            "old_price": r["old_price"],
            "new_price": r["new_price"],
            "change": r["new_price"] - r["old_price"],
            "change_pct": round(
                (r["new_price"] - r["old_price"]) / r["old_price"] * 100, 1
            ) if r["old_price"] else 0,
            "recorded_at": r["recorded_at"].isoformat(),
        })
    return result


async def get_batch_days_on_market(property_ids: list[str]) -> dict[str, int]:
    """Get days on market for multiple listings in a single query.

    Returns a dict mapping property_id → days on market (int).
    """
    if not property_ids:
        return {}

    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, first_seen_at
            FROM properties
            WHERE id = ANY($1::text[])
              AND first_seen_at IS NOT NULL
            """,
            property_ids,
        )

    return {
        r["id"]: (now - r["first_seen_at"]).days
        for r in rows
        if r["first_seen_at"]
    }
