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
