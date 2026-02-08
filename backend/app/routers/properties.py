"""Property search API endpoints."""

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from housemktanalyzr.collectors.centris import CentrisScraper
from housemktanalyzr.models.property import PropertyListing, PropertyType

from ..constants import PROPERTY_TYPE_URLS, REGION_URL_MAPPING

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/price-changes")
async def get_recent_price_changes():
    """Get recent price changes across all active listings (for badges)."""
    if not _has_db():
        return {"changes": {}}

    try:
        from ..db import get_recent_price_changes as db_get_changes
        changes = await db_get_changes()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get price changes: {str(e)}")

    # Return as a dict keyed by property_id for O(1) lookup in frontend
    return {
        "changes": {
            c["property_id"]: {
                "old_price": c["old_price"],
                "new_price": c["new_price"],
                "change": c["change"],
                "change_pct": c["change_pct"],
                "recorded_at": c["recorded_at"],
            }
            for c in changes
        }
    }


@router.get("/lifecycle")
async def get_batch_lifecycle():
    """Get lifecycle data (status, DOM, first_seen) for all listings.

    Returns a map of property_id → {status, days_on_market, first_seen_at}
    for active, stale, and recently-delisted listings.
    """
    if not _has_db():
        return {"listings": {}}

    try:
        from ..db import get_batch_lifecycle as db_get_lifecycle
        items = await db_get_lifecycle()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get lifecycle data: {str(e)}")

    return {
        "listings": {
            item["id"]: {
                "status": item["status"],
                "days_on_market": item["days_on_market"],
                "first_seen_at": item["first_seen_at"],
                "last_seen_at": item["last_seen_at"],
            }
            for item in items
        }
    }


@router.get("/recently-removed")
async def get_recently_removed(
    region: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get listings that were recently delisted (disappeared from Centris).

    Returns properties with status 'stale' or 'delisted' that were
    last seen within the past 7 days.
    """
    if not _has_db():
        return {"listings": [], "count": 0}

    try:
        from ..db import get_pool
        import json

        pool = get_pool()
        async with pool.acquire() as conn:
            params: list = []
            idx = 1

            conditions = [
                "status IN ('stale', 'delisted')",
                "last_seen_at > NOW() - INTERVAL '7 days'",
            ]
            if region:
                conditions.append(f"region = ${idx}")
                params.append(region)
                idx += 1

            where = " AND ".join(conditions)
            query = f"""
                SELECT data, status, first_seen_at, last_seen_at, price
                FROM properties
                WHERE {where}
                ORDER BY last_seen_at DESC
                LIMIT ${idx}
            """
            params.append(limit)
            rows = await conn.fetch(query, *params)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        results = []
        for row in rows:
            listing_data = json.loads(row["data"])
            first_seen = row["first_seen_at"]
            results.append({
                "listing": listing_data,
                "status": row["status"],
                "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                "days_on_market": (now - first_seen).days if first_seen else None,
            })

        return {"listings": results, "count": len(results)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get removed listings: {str(e)}")


def _has_db() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


class PropertySearchResponse(BaseModel):
    """Response containing search results."""
    listings: list[PropertyListing]
    count: int
    region: str
    cached: bool = False


@router.get("/search", response_model=PropertySearchResponse)
async def search_properties(
    region: str = Query(default="montreal", description="Region to search"),
    property_types: Optional[str] = Query(
        default=None,
        description="Comma-separated property types (DUPLEX,TRIPLEX,QUADPLEX,MULTIPLEX,HOUSE)",
    ),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    enrich: bool = Query(default=False, description="Fetch full listing details"),
) -> PropertySearchResponse:
    """Search for property listings. Returns DB results when available."""
    types_list = None
    if property_types:
        types_list = [t.strip().upper() for t in property_types.split(",")]
        valid_types = {"DUPLEX", "TRIPLEX", "QUADPLEX", "MULTIPLEX", "HOUSE"}
        invalid = set(types_list) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid property types: {invalid}. Valid types: {valid_types}",
            )

    # DB-first: query Postgres for cached listings
    if _has_db():
        try:
            from ..db import get_cached_listings
            cached = await get_cached_listings(
                property_types=types_list, min_price=min_price,
                max_price=max_price, region=region, limit=limit,
            )
            if cached:
                listings = [PropertyListing(**d) for d in cached]
                logger.info(f"DB hit: {len(listings)} listings for {region}")
                return PropertySearchResponse(
                    listings=listings, count=len(listings), region=region, cached=True,
                )
        except Exception as e:
            logger.warning(f"DB read failed, falling back to scraper: {e}")

    # Fallback: scrape only if DB is empty (first run or no data yet)
    try:
        async with CentrisScraper() as scraper:
            if enrich:
                listings = await scraper.fetch_listings_with_details(
                    region=region, property_types=types_list,
                    min_price=min_price, max_price=max_price, limit=limit,
                )
            else:
                listings = await scraper.fetch_listings(
                    region=region, property_types=types_list,
                    min_price=min_price, max_price=max_price, limit=limit,
                )

        if _has_db() and listings:
            try:
                from ..db import cache_listings
                await cache_listings(listings, region=region)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

        return PropertySearchResponse(
            listings=listings, count=len(listings), region=region,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/multi-type", response_model=PropertySearchResponse)
async def search_multi_type(
    region: str = Query(default="montreal"),
    property_types: Optional[str] = Query(
        default="DUPLEX,TRIPLEX,QUADPLEX",
        description="Comma-separated property types",
    ),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    enrich: bool = Query(default=False),
) -> PropertySearchResponse:
    """Search across multiple property types. Returns all matching DB results."""
    types_list = None
    if property_types:
        types_list = [t.strip().upper() for t in property_types.split(",")]

    # DB-first — no limit, frontend handles pagination
    if _has_db():
        try:
            from ..db import get_cached_listings
            cached = await get_cached_listings(
                property_types=types_list, min_price=min_price,
                max_price=max_price, region=region, limit=10000,
            )
            if cached:
                listings = [PropertyListing(**d) for d in cached]
                logger.info(f"DB hit: {len(listings)} listings for {region}")
                return PropertySearchResponse(
                    listings=listings, count=len(listings), region=region, cached=True,
                )
        except Exception as e:
            logger.warning(f"DB read failed, falling back to scraper: {e}")

    # Fallback
    try:
        async with CentrisScraper() as scraper:
            listings = await scraper.fetch_listings_multi_type(
                region=region, property_types=types_list,
                enrich=enrich, min_price=min_price, max_price=max_price,
            )

        if _has_db() and listings:
            try:
                from ..db import cache_listings
                await cache_listings(listings, region=region)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

        return PropertySearchResponse(
            listings=listings, count=len(listings), region=region,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-type search failed: {str(e)}")


class AllListingsResponse(BaseModel):
    """Response containing all listings from paginated search."""
    listings: list[PropertyListing]
    count: int
    region: str
    pages_fetched: int


@router.get("/all-listings", response_model=AllListingsResponse)
async def get_all_listings(
    region: str = Query(default="montreal", description="Region to search"),
    property_type: str = Query(
        default="ALL_PLEX",
        description="Property type: DUPLEX, TRIPLEX, HOUSE, or ALL_PLEX",
    ),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    max_pages: int = Query(default=10, ge=1, le=20),
    enrich: bool = Query(default=False),
) -> AllListingsResponse:
    """Fetch ALL listings using AJAX pagination. Use /search for normal queries."""
    url_pattern = PROPERTY_TYPE_URLS.get(property_type.upper())
    if not url_pattern:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid property_type: {property_type}. Valid: {list(PROPERTY_TYPE_URLS.keys())}",
        )

    region_slug = REGION_URL_MAPPING.get(region.lower())
    if not region_slug:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region: {region}. Valid: {list(REGION_URL_MAPPING.keys())}",
        )

    search_url = f"https://www.centris.ca{url_pattern.format(region=region_slug)}"

    try:
        async with CentrisScraper() as scraper:
            listings = await scraper.fetch_all_listings(
                search_url=search_url, enrich=enrich,
                min_price=min_price, max_price=max_price, max_pages=max_pages,
            )

        if _has_db() and listings:
            try:
                from ..db import cache_listings, DETAIL_CACHE_TTL_HOURS
                await cache_listings(listings, ttl_hours=DETAIL_CACHE_TTL_HOURS, region=region)
            except Exception as e:
                logger.warning(f"Cache write failed: {e}")

        return AllListingsResponse(
            listings=listings, count=len(listings), region=region,
            pages_fetched=min(max_pages, (len(listings) // 20) + 1),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"All-listings search failed: {str(e)}")


@router.get("/{listing_id}/price-history")
async def get_price_history(listing_id: str):
    """Get price change history for a specific listing."""
    normalized_id = listing_id.strip()
    if normalized_id.isdigit():
        normalized_id = f"centris-{normalized_id}"

    if not _has_db():
        return {"property_id": normalized_id, "changes": [], "total_change": 0, "total_change_pct": 0}

    try:
        from ..db import get_price_history as db_get_price_history, get_listing_lifecycle
        changes = await db_get_price_history(normalized_id)
        lifecycle = await get_listing_lifecycle(normalized_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get price history: {str(e)}")

    total_change = 0
    total_change_pct = 0.0
    original_price = None
    current_price = lifecycle["current_price"] if lifecycle else None

    if changes:
        # changes are newest-first; oldest change has the original price
        original_price = changes[-1]["old_price"]
        if current_price and original_price:
            total_change = current_price - original_price
            total_change_pct = round(total_change / original_price * 100, 1)

    return {
        "property_id": normalized_id,
        "current_price": current_price,
        "original_price": original_price,
        "total_change": total_change,
        "total_change_pct": total_change_pct,
        "changes": changes,
        "days_on_market": lifecycle["days_on_market"] if lifecycle else None,
        "status": lifecycle["status"] if lifecycle else "active",
        "first_seen_at": lifecycle["first_seen_at"] if lifecycle else None,
    }


@router.get("/{listing_id}", response_model=PropertyListing)
async def get_property_details(
    listing_id: str,
    force_walkscore: bool = Query(default=False, description="Force re-fetch Walk Score"),
    force_condition: bool = Query(default=False, description="Force re-score condition via AI"),
) -> PropertyListing:
    """Get full details for a specific listing by MLS # or centris-{id}.

    Accepts raw MLS numbers (e.g. 28574831) or prefixed IDs (centris-28574831).
    Checks DB first, then falls back to live Centris scrape.
    """
    # Normalize: raw digits → centris-{digits}
    normalized_id = listing_id.strip()
    if normalized_id.isdigit():
        normalized_id = f"centris-{normalized_id}"

    listing = None

    if _has_db():
        try:
            from ..db import get_cached_listing
            cached = await get_cached_listing(normalized_id)
            if cached:
                listing = PropertyListing(**cached)
        except Exception as e:
            logger.warning(f"DB read failed: {e}")

    if listing is None:
        try:
            async with CentrisScraper() as scraper:
                listing = await scraper.get_listing_details(normalized_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get details: {str(e)}")

        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

    # Enrich with Walk Score if not already populated (or forced)
    if listing.walk_score is None or force_walkscore:
        try:
            from housemktanalyzr.enrichment.walkscore import enrich_with_walk_score

            result = await enrich_with_walk_score(
                address=listing.address,
                city=listing.city,
                latitude=listing.latitude,
                longitude=listing.longitude,
            )
            if result:
                listing.walk_score = result.walk_score
                listing.transit_score = result.transit_score
                listing.bike_score = result.bike_score
                listing.latitude = result.latitude
                listing.longitude = result.longitude
        except Exception as e:
            logger.warning(f"Walk Score enrichment failed: {e}")

    # Fetch photos if not available (listing might be from search cards only)
    if not listing.photo_urls:
        try:
            async with CentrisScraper() as scraper:
                detailed = await scraper.get_listing_details(listing.id, url=listing.url)
                if detailed and detailed.photo_urls:
                    listing.photo_urls = detailed.photo_urls
        except Exception as e:
            logger.warning(f"Photo extraction failed: {e}")

    # Enrich with AI condition score if not already populated (or forced)
    if (listing.condition_score is None or force_condition) and listing.photo_urls:
        try:
            from housemktanalyzr.enrichment.condition_scorer import score_property_condition

            result = await score_property_condition(
                photo_urls=listing.photo_urls,
                property_type=listing.property_type.value,
                city=listing.city,
                year_built=listing.year_built,
            )
            if result:
                listing.condition_score = result.overall_score
                listing.condition_details = {
                    "kitchen": result.kitchen_score,
                    "bathroom": result.bathroom_score,
                    "floors": result.floors_score,
                    "exterior": result.exterior_score,
                    "renovation_needed": result.renovation_needed,
                    "notes": result.notes,
                }
        except Exception as e:
            logger.warning(f"Condition scoring failed: {e}")

    # Cache (or re-cache with enriched data)
    if _has_db():
        try:
            from ..db import cache_listings, DETAIL_CACHE_TTL_HOURS
            await cache_listings([listing], ttl_hours=DETAIL_CACHE_TTL_HOURS)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    return listing
