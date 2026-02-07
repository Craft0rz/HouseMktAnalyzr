"""Property search API endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from housemktanalyzr.collectors.centris import CentrisScraper
from housemktanalyzr.models.property import PropertyListing, PropertyType

router = APIRouter()


class PropertySearchParams(BaseModel):
    """Search parameters for property listings."""

    region: str = Field(default="montreal", description="Region to search")
    property_types: Optional[list[str]] = Field(
        default=None, description="Filter by property types (DUPLEX, TRIPLEX, etc.)"
    )
    min_price: Optional[int] = Field(default=None, ge=0, description="Minimum price")
    max_price: Optional[int] = Field(default=None, ge=0, description="Maximum price")
    limit: Optional[int] = Field(default=20, ge=1, le=100, description="Max results")
    enrich: bool = Field(
        default=False, description="Fetch full details (slower but more data)"
    )


class PropertySearchResponse(BaseModel):
    """Response containing search results."""

    listings: list[PropertyListing]
    count: int
    region: str


@router.get("/search", response_model=PropertySearchResponse)
async def search_properties(
    region: str = Query(default="montreal", description="Region to search"),
    property_types: Optional[str] = Query(
        default=None,
        description="Comma-separated property types (DUPLEX,TRIPLEX,QUADPLEX,MULTIPLEX,HOUSE)",
    ),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    enrich: bool = Query(default=False, description="Fetch full listing details"),
) -> PropertySearchResponse:
    """Search for property listings.

    Fetches property listings from Centris.ca based on search criteria.
    Use enrich=true to get full details (sqft, year built, taxes) but be
    aware this is slower as it fetches each listing's detail page.
    """
    # Parse property types
    types_list = None
    if property_types:
        types_list = [t.strip().upper() for t in property_types.split(",")]
        # Validate types
        valid_types = {"DUPLEX", "TRIPLEX", "QUADPLEX", "MULTIPLEX", "HOUSE"}
        invalid = set(types_list) - valid_types
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid property types: {invalid}. Valid types: {valid_types}",
            )

    try:
        async with CentrisScraper() as scraper:
            if enrich:
                listings = await scraper.fetch_listings_with_details(
                    region=region,
                    property_types=types_list,
                    min_price=min_price,
                    max_price=max_price,
                    limit=limit,
                )
            else:
                listings = await scraper.fetch_listings(
                    region=region,
                    property_types=types_list,
                    min_price=min_price,
                    max_price=max_price,
                    limit=limit,
                )

        return PropertySearchResponse(
            listings=listings,
            count=len(listings),
            region=region,
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
    """Search across multiple property types for more results.

    This endpoint uses property-type specific URLs to get more listings
    than a single search (Centris returns ~20 per search page).
    """
    types_list = None
    if property_types:
        types_list = [t.strip().upper() for t in property_types.split(",")]

    try:
        async with CentrisScraper() as scraper:
            listings = await scraper.fetch_listings_multi_type(
                region=region,
                property_types=types_list,
                enrich=enrich,
                min_price=min_price,
                max_price=max_price,
            )

        return PropertySearchResponse(
            listings=listings,
            count=len(listings),
            region=region,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-type search failed: {str(e)}")


class AllListingsResponse(BaseModel):
    """Response containing all listings from paginated search."""

    listings: list[PropertyListing]
    count: int
    region: str
    pages_fetched: int


# URL patterns for property-type specific searches
PROPERTY_TYPE_URLS = {
    "DUPLEX": "/en/duplexes~for-sale~{region}",
    "TRIPLEX": "/en/triplexes~for-sale~{region}",
    "HOUSE": "/en/houses~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",  # All multi-family
}

# Region name mappings for URL construction
REGION_URL_MAPPING = {
    "montreal": "montreal-island",
    "laval": "laval",
    "longueuil": "longueuil",
    "south-shore": "montreal-south-shore",
    "rive-sud": "montreal-south-shore",
    "monteregie": "monteregie",
    "north-shore": "north-shore",
    "laurentides": "laurentides",
    "lanaudiere": "lanaudiere",
}


@router.get("/all-listings", response_model=AllListingsResponse)
async def get_all_listings(
    region: str = Query(default="montreal", description="Region to search"),
    property_type: str = Query(
        default="ALL_PLEX",
        description="Property type: DUPLEX, TRIPLEX, HOUSE, or ALL_PLEX (all multi-family)",
    ),
    min_price: Optional[int] = Query(default=None, ge=0),
    max_price: Optional[int] = Query(default=None, ge=0),
    max_pages: int = Query(default=10, ge=1, le=20, description="Max pages to fetch (20 listings per page)"),
    enrich: bool = Query(default=False, description="Fetch full listing details (slower)"),
) -> AllListingsResponse:
    """Fetch ALL listings using AJAX pagination for comprehensive results.

    This endpoint uses Centris's internal pagination API to retrieve many more
    results than the standard search (which only returns ~20). It can fetch
    up to 400 listings (20 pages × 20 per page).

    Use this for comprehensive searches when you need more than 20 listings.
    Note: Higher max_pages = more results but slower response time.
    """
    # Map property type to URL pattern
    url_pattern = PROPERTY_TYPE_URLS.get(property_type.upper())
    if not url_pattern:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid property_type: {property_type}. Valid types: {list(PROPERTY_TYPE_URLS.keys())}",
        )

    # Map region to URL slug
    region_slug = REGION_URL_MAPPING.get(region.lower())
    if not region_slug:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid region: {region}. Valid regions: {list(REGION_URL_MAPPING.keys())}",
        )

    # Build search URL
    search_url = f"https://www.centris.ca{url_pattern.format(region=region_slug)}"

    try:
        async with CentrisScraper() as scraper:
            listings = await scraper.fetch_all_listings(
                search_url=search_url,
                enrich=enrich,
                min_price=min_price,
                max_price=max_price,
                max_pages=max_pages,
            )

        return AllListingsResponse(
            listings=listings,
            count=len(listings),
            region=region,
            pages_fetched=min(max_pages, (len(listings) // 20) + 1),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"All-listings search failed: {str(e)}")


@router.get("/{listing_id}", response_model=PropertyListing)
async def get_property_details(listing_id: str) -> PropertyListing:
    """Get full details for a specific listing.

    Fetches the listing detail page and returns comprehensive data
    including square footage, year built, taxes, and assessment.
    """
    try:
        async with CentrisScraper() as scraper:
            listing = await scraper.get_listing_details(listing_id)

        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        return listing

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get details: {str(e)}")
