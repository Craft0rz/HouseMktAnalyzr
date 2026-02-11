"""Centris.ca web scraper data source.

This module implements a web scraper for Centris.ca, the primary MLS listing
platform for Quebec real estate. It uses httpx for async HTTP requests and
BeautifulSoup for HTML parsing.

Note: Centris uses JavaScript-heavy rendering and AJAX for pagination.
This scraper interacts with their internal API endpoints to fetch listing data.

References:
    - https://github.com/harshhes/centris-ca-scrape
    - https://github.com/enesrizaates/centris.ca-crawler
"""

import asyncio
import hashlib
import logging
import os
import re
from datetime import date
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from ..models.property import PropertyListing, PropertyType
from .base import CaptchaError, DataSource, DataSourceError, RateLimitError

logger = logging.getLogger(__name__)


# Mapping of region names to Centris search URLs/parameters
REGION_MAPPING = {
    "montreal": "Montreal (Island)",
    "laval": "Laval",
    "south-shore": "South Shore",
    "laurentides": "Laurentides",
    "lanaudiere": "Lanaudière",
    "capitale-nationale": "Capitale-Nationale",
    "estrie": "Estrie",
}

# Mapping of property types to Centris property type codes
PROPERTY_TYPE_MAPPING = {
    "HOUSE": ["Detached", "Bungalow", "Cottage", "Two or more storeys"],
    "DUPLEX": ["Duplex"],
    "TRIPLEX": ["Triplex"],
    "QUADPLEX": ["Quadruplex"],
    "MULTIPLEX": ["Quintuplex or more", "Multi-family (5+)"],
}

# Full type-to-URL mapping for on-demand searches.
# DUPLEX/TRIPLEX have dedicated Centris URLs; QUADPLEX/MULTIPLEX fall back to ALL_PLEX.
PROPERTY_TYPE_URLS = {
    "HOUSE": "/en/houses~for-sale~{region}",
    "DUPLEX": "/en/duplexes~for-sale~{region}",
    "TRIPLEX": "/en/triplexes~for-sale~{region}",
    "QUADPLEX": "/en/plexes~for-sale~{region}",
    "MULTIPLEX": "/en/plexes~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",
}

# Region name mappings for URL construction — uses Centris Geographic Areas (Level 1 only).
# Avoids Level 2 sub-areas (e.g. montreal-north-shore) to prevent overlap.
# See sitemap: propertysubtype-sellingtype-geographicarea-1.xml
REGION_URL_MAPPING = {
    "montreal": "montreal-island",
    "laval": "laval",
    "south-shore": "monteregie",      # full Montérégie geographic area
    "rive-sud": "monteregie",
    "laurentides": "laurentides",
    "lanaudiere": "lanaudiere",
    "capitale-nationale": "capitale-nationale",
    "estrie": "estrie",
}


class CentrisScraper(DataSource):
    """Web scraper for Centris.ca property listings.

    This scraper fetches property listings from Centris.ca by interacting
    with their internal API. It implements rate limiting and handles common
    issues like CAPTCHAs and connection errors.

    Attributes:
        name: "centris"
        priority: 1 (high priority - primary Quebec data source)

    Example:
        scraper = CentrisScraper()
        if scraper.is_available():
            listings = await scraper.fetch_listings(
                region="montreal",
                property_types=["DUPLEX", "TRIPLEX"],
                min_price=300000,
                max_price=800000,
                limit=50
            )
    """

    name = "centris"
    priority = 1

    # Centris base URLs
    BASE_URL = "https://www.centris.ca"
    SEARCH_URL = "https://www.centris.ca/en/properties~for-sale"
    API_URL = "https://www.centris.ca/Property/GetInscriptions"

    # Rate limiting settings
    MIN_REQUEST_INTERVAL = 1.0  # seconds between requests
    MAX_RETRIES = 3
    BACKOFF_FACTOR = 2.0

    def __init__(
        self,
        request_interval: float = 1.0,
        timeout: float = 30.0,
        user_agent: Optional[str] = None,
    ):
        """Initialize the Centris scraper.

        Args:
            request_interval: Minimum seconds between requests (default 1.0)
            timeout: Request timeout in seconds (default 30.0)
            user_agent: Custom User-Agent string (uses default if None)
        """
        self.request_interval = max(request_interval, self.MIN_REQUEST_INTERVAL)
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/133.0.0.0 Safari/537.36"
        )
        self._last_request_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Charset": "utf-8",
                    "Connection": "keep-alive",
                },
                follow_redirects=True,
            )
        return self._client

    async def _get_page_with_browser(self, url: str) -> Optional[str]:
        """Fetch a page using Playwright headless Chromium for JS-rendered content.

        Returns the fully rendered HTML string, or None if Playwright is not
        available or browser launch fails. Caller should fall back to httpx.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    context = await browser.new_context(
                        user_agent=self.user_agent,
                        viewport={"width": 1920, "height": 1080},
                    )
                    page = await context.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    # Wait for gallery images to load
                    try:
                        await page.wait_for_selector(
                            "img[src*='media.ashx'], img[data-src*='media.ashx']",
                            timeout=5000,
                        )
                    except Exception:
                        pass  # Photos may not be present on every page
                    html = await page.content()
                    return html
                finally:
                    await browser.close()
        except Exception as e:
            logger.warning(f"Playwright fetch failed for {url}: {e}")
            return None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        import time

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.request_interval:
            await asyncio.sleep(self.request_interval - elapsed)
        self._last_request_time = time.time()

    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a rate-limited HTTP request with retry logic.

        Args:
            url: The URL to request
            method: HTTP method (GET or POST)
            **kwargs: Additional arguments passed to httpx

        Returns:
            httpx.Response object

        Raises:
            CaptchaError: If a CAPTCHA is detected
            RateLimitError: If rate limit is exceeded after retries
            DataSourceError: For other request errors
        """
        client = await self._get_client()

        for attempt in range(self.MAX_RETRIES):
            await self._rate_limit()

            try:
                if method.upper() == "POST":
                    response = await client.post(url, **kwargs)
                else:
                    response = await client.get(url, **kwargs)

                # Check for CAPTCHA
                if self._is_captcha_response(response):
                    raise CaptchaError(self.name)

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(
                            retry_after * (self.BACKOFF_FACTOR**attempt)
                        )
                        continue
                    raise RateLimitError(self.name, retry_after)

                response.raise_for_status()
                return response

            except httpx.TimeoutException:
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BACKOFF_FACTOR**attempt)
                    continue
                raise DataSourceError(self.name, "Request timeout after retries")

            except httpx.HTTPStatusError as e:
                raise DataSourceError(self.name, f"HTTP error: {e.response.status_code}")

        raise DataSourceError(self.name, "Max retries exceeded")

    def _is_captcha_response(self, response: httpx.Response) -> bool:
        """Check if the response contains a CAPTCHA challenge.

        Note: We check for actual CAPTCHA challenges, not just script references.
        Centris pages normally include recaptcha.js but that doesn't mean we're blocked.

        Uses multiple validity indicators to avoid false positives when Centris
        changes CSS class names.
        """
        content = response.text.lower()

        # Multiple indicators that this is a valid Centris page (not a CAPTCHA).
        # If ANY of these are present, it's a real page — not a challenge.
        valid_page_indicators = [
            "property-thumbnail-item",       # Search result card class
            "property-thumbnail-summary",    # Card summary class
            "carac-container",               # Detail page characteristic section
            "itemprop=\"price\"",            # Schema.org price metadata
            "centris.ca/media.ashx",         # Centris media/photo URLs
            "data-mlsnumber",                # MLS number data attribute
            "inscription-address",           # Listing address section
            "resultcount",                   # Search results count element
        ]
        if any(indicator in content for indicator in valid_page_indicators):
            return False

        # Also check response metadata: real pages are substantial
        # CAPTCHA challenge pages are typically small (<5KB)
        if len(response.content) > 10000 and response.status_code == 200:
            # Large 200 response — likely a real page even if we can't find markers
            return False

        # Check for actual CAPTCHA challenge indicators (not just script refs)
        captcha_challenge_indicators = [
            "g-recaptcha-response",  # Actual reCAPTCHA widget
            "please verify you are human",
            "i'm not a robot",
            "captcha-container",
            "challenge-form",
            "cf-challenge",  # Cloudflare challenge
            "access denied",
        ]
        return any(indicator in content for indicator in captcha_challenge_indicators)

    def _parse_price(self, price_str: str) -> Optional[int]:
        """Parse price string to integer."""
        if not price_str:
            return None
        # Remove currency symbols, spaces, and commas
        cleaned = re.sub(r"[^\d]", "", price_str)
        try:
            return int(cleaned) if cleaned else None
        except ValueError:
            return None

    def _parse_bedrooms(self, text: str) -> int:
        """Parse bedroom count from text."""
        if not text:
            return 0
        # Look for patterns like "3 bdr", "3 beds", "3 ch"
        match = re.search(r"(\d+)\s*(?:bdr|bed|ch|chambre)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        # Try just a number
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0

    def _parse_bathrooms(self, text: str) -> float:
        """Parse bathroom count from text."""
        if not text:
            return 0.0
        # Look for patterns like "2 bath", "1.5 sdb"
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bath|sdb|salle)", text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        # Try just a number
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        return float(match.group(1)) if match else 0.0

    def _parse_sqft(self, text: str) -> Optional[int]:
        """Parse square footage from text."""
        if not text:
            return None
        # Look for patterns like "1500 sqft", "1500 sq ft", "1500 pi2"
        match = re.search(
            r"(\d[\d,]*)\s*(?:sqft|sq\.?\s*ft|pi2|pieds?)", text, re.IGNORECASE
        )
        if match:
            return int(match.group(1).replace(",", ""))
        return None

    def _determine_property_type(self, type_text: str, units: int) -> PropertyType:
        """Determine property type from listing text and unit count."""
        type_lower = type_text.lower()

        if "duplex" in type_lower or units == 2:
            return PropertyType.DUPLEX
        elif "triplex" in type_lower or units == 3:
            return PropertyType.TRIPLEX
        elif "quadruplex" in type_lower or "quadplex" in type_lower or units == 4:
            return PropertyType.QUADPLEX
        elif "quintuplex" in type_lower or "multi" in type_lower or units >= 5:
            return PropertyType.MULTIPLEX
        else:
            return PropertyType.HOUSE

    def _generate_listing_id(self, url: str, address: str) -> str:
        """Generate a unique listing ID from URL and address."""
        # Try to extract Centris ID from URL
        match = re.search(r"/(\d{7,})", url)
        if match:
            return f"centris-{match.group(1)}"
        # Fallback to hash
        content = f"{url}:{address}"
        return f"centris-{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def _parse_listing_card(self, card: BeautifulSoup) -> Optional[PropertyListing]:
        """Parse a single listing card from the search results page.

        Centris HTML structure:
        - .address contains two child <div>: street (first) and city (second)
        - .cac = bedrooms (chambres à coucher)
        - .sdb = bathrooms (salles de bain)
        - .price = price display
        - meta[itemprop="price"] = raw price value
        - meta[itemprop="sku"] or data-mlsnumber attribute = MLS ID

        Note: Square footage is NOT available in search result cards.
        It would require fetching individual listing details.

        Args:
            card: BeautifulSoup element containing the listing card

        Returns:
            PropertyListing or None if parsing fails
        """
        try:
            # Extract MLS ID - try multiple sources
            mls_id = card.get("data-mlsnumber", "")
            if not mls_id:
                # Try meta[itemprop="sku"]
                sku_meta = card.find("meta", itemprop="sku")
                if sku_meta:
                    mls_id = sku_meta.get("content", "")
            if not mls_id:
                # Try link with data-mlsnumber
                mls_link = card.find("a", attrs={"data-mlsnumber": True})
                if mls_link:
                    mls_id = mls_link.get("data-mlsnumber", "")

            # Extract URL
            link = card.find("a", class_="property-thumbnail-summary-link")
            if not link:
                link = card.find("a", href=re.compile(r"/en/"))
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            # Extract thumbnail photo URL from card image
            thumbnail_url = None
            img_elem = card.find("img")
            if img_elem:
                img_url = img_elem.get("data-src") or img_elem.get("src") or ""
                if img_url and ("centris.ca" in img_url or "media.ashx" in img_url):
                    if not img_url.startswith("http"):
                        img_url = f"{self.BASE_URL}{img_url}"
                    thumbnail_url = img_url

            # Extract address - Centris uses .address with two child divs
            address_elem = card.find(class_="address")
            street = ""
            city = "Montreal"  # Default

            if address_elem:
                # Find child divs - first is street, second is city
                address_divs = address_elem.find_all("div", recursive=False)
                if len(address_divs) >= 2:
                    street = address_divs[0].get_text(strip=True)
                    city = address_divs[1].get_text(strip=True)
                elif len(address_divs) == 1:
                    street = address_divs[0].get_text(strip=True)
                else:
                    # Fallback to direct text
                    street = address_elem.get_text(strip=True)

            # Combine address
            address_text = street if street else "Unknown"

            # Extract price - try meta tag first (raw value), then .price element
            price = None
            price_meta = card.find("meta", itemprop="price")
            if price_meta:
                price = self._parse_price(price_meta.get("content", ""))

            if not price:
                price_elem = card.find(class_="price")
                if price_elem:
                    price = self._parse_price(price_elem.get_text(strip=True))

            if not price:
                return None  # Skip listings without price

            # Extract bedrooms from .cac element (chambres à coucher)
            bedrooms = 0
            cac_elem = card.find(class_="cac")
            if cac_elem:
                cac_text = cac_elem.get_text(strip=True)
                match = re.search(r"(\d+)", cac_text)
                if match:
                    bedrooms = int(match.group(1))

            # Extract bathrooms from .sdb element (salles de bain)
            bathrooms = 0.0
            sdb_elem = card.find(class_="sdb")
            if sdb_elem:
                sdb_text = sdb_elem.get_text(strip=True)
                match = re.search(r"(\d+(?:\.\d+)?)", sdb_text)
                if match:
                    bathrooms = float(match.group(1))

            # Extract square footage from teaser/description
            sqft = None
            teaser_elem = card.find(class_="teaser")
            if teaser_elem:
                sqft = self._parse_sqft(teaser_elem.get_text())

            # Determine property type from category
            type_elem = card.find(class_="category")
            type_text = type_elem.get_text(strip=True) if type_elem else ""

            # Count units for multi-family
            units = 1
            details_text = card.get_text(" ", strip=True)
            unit_match = re.search(r"(\d+)\s*(?:unit|logement)", details_text, re.IGNORECASE)
            if unit_match:
                units = int(unit_match.group(1))
            elif "duplex" in type_text.lower():
                units = 2
            elif "triplex" in type_text.lower():
                units = 3
            elif "quadruplex" in type_text.lower():
                units = 4
            elif "quintuplex" in type_text.lower() or "5-plex" in type_text.lower():
                units = 5
            else:
                # Try extracting from "(N)" in category text, e.g. "Residential (6)"
                paren_match = re.search(r"\((\d+)\)", type_text)
                if paren_match:
                    units = int(paren_match.group(1))
                # Also try URL for plex type hints
                elif url:
                    url_lower = url.lower()
                    if "5plex" in url_lower or "quintuplex" in url_lower:
                        units = 5
                    elif "plex" in url_lower and units == 1:
                        # Generic plex URL — extract digit before "plex" if present
                        plex_match = re.search(r"(\d+)plex", url_lower)
                        if plex_match:
                            units = int(plex_match.group(1))

            property_type = self._determine_property_type(type_text, units)

            # P0 fix: Ensure unit count is consistent with property type.
            # If detection failed (units=1) but type is known plex, use type as fallback.
            _TYPE_MIN_UNITS = {
                PropertyType.DUPLEX: 2,
                PropertyType.TRIPLEX: 3,
                PropertyType.QUADPLEX: 4,
                PropertyType.MULTIPLEX: 5,
            }
            min_units = _TYPE_MIN_UNITS.get(property_type)
            if min_units and units < min_units:
                units = min_units

            # Generate ID - prefer MLS ID
            if mls_id:
                listing_id = f"centris-{mls_id}"
            else:
                listing_id = self._generate_listing_id(url, address_text)

            return PropertyListing(
                id=listing_id,
                source=self.name,
                address=address_text,
                city=city,
                postal_code=None,  # Often not shown in search results
                price=price,
                property_type=property_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                sqft=sqft,
                lot_sqft=None,
                year_built=None,
                units=units,
                estimated_rent=None,
                listing_date=None,
                url=url or self.SEARCH_URL,
                photo_urls=[thumbnail_url] if thumbnail_url else None,
                raw_data={"mls_id": mls_id} if mls_id else None,
            )

        except Exception as e:
            logger.warning(f"Failed to parse listing card: {e}")
            return None

    async def _fetch_search_page(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        page: int = 1,
    ) -> list[PropertyListing]:
        """Fetch a single page of search results.

        Args:
            region: Region to search
            property_types: Property type filters
            min_price: Minimum price
            max_price: Maximum price
            page: Page number (1-indexed)

        Returns:
            List of PropertyListing objects from this page
        """
        # Build search URL with filters
        url = self.SEARCH_URL

        # Add region filter
        region_name = REGION_MAPPING.get(region.lower(), region)

        # Centris uses query parameters for filtering
        params = {
            "view": "List",
            "uc": "1",  # Include commercial? Set to 0 for residential only
        }

        if min_price:
            params["minPrice"] = str(min_price)
        if max_price:
            params["maxPrice"] = str(max_price)

        # Make request
        try:
            response = await self._make_request(url, params=params)
            # Use content with explicit UTF-8 to properly handle French characters
            soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")

            # Find listing cards
            listings = []

            # Centris uses various class names for listing cards
            card_selectors = [
                "div.property-thumbnail-item",
                "div.thumbnail-item",
                "div.property-item",
                "article.listing",
                "div[data-listing-id]",
            ]

            cards = []
            for selector in card_selectors:
                cards = soup.select(selector)
                if cards:
                    break

            # If no cards found, try finding by common patterns
            if not cards:
                cards = soup.find_all(
                    "div",
                    class_=re.compile(r"property|listing|result", re.IGNORECASE),
                )

            seen_ids = set()
            for card in cards:
                listing = self._parse_listing_card(card)
                if listing:
                    # Skip duplicates
                    if listing.id in seen_ids:
                        continue
                    seen_ids.add(listing.id)

                    # Apply property type filter
                    if property_types:
                        if listing.property_type.value not in property_types:
                            continue
                    listings.append(listing)

            return listings

        except (CaptchaError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error fetching search page: {e}")
            return []

    async def fetch_listings(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[PropertyListing]:
        """Fetch property listings from Centris.ca.

        Args:
            region: Geographic region (e.g., "montreal", "laval")
            property_types: Filter by types (e.g., ["DUPLEX", "TRIPLEX"])
            min_price: Minimum price in CAD
            max_price: Maximum price in CAD
            limit: Maximum listings to return (default: 100)

        Returns:
            List of PropertyListing objects

        Raises:
            CaptchaError: If CAPTCHA is encountered
            RateLimitError: If rate limited after retries
            DataSourceError: For other errors
        """
        limit = limit or 100

        logger.info(
            f"Fetching Centris listings: region={region}, "
            f"types={property_types}, price={min_price}-{max_price}"
        )

        # Note: Centris uses infinite scroll/AJAX for pagination, not URL params.
        # For now, we only fetch the first page (20 listings).
        # TODO: Implement AJAX-based pagination for more results.
        page_listings = await self._fetch_search_page(
            region=region,
            property_types=property_types,
            min_price=min_price,
            max_price=max_price,
            page=1,
        )

        # Apply limit
        result = page_listings[:limit]
        logger.info(f"Found {len(result)} listings from Centris")

        return result

    def _extract_photo_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract photo gallery URLs from a Centris detail page.

        Combines multiple strategies to find all listing photos:
        1. Gallery/carousel container images (CSS selectors)
        2. All img tags with Centris media URLs
        3. JSON data embedded in script tags

        Filters to only keep actual photos (t=pi param), not thumbnails.
        """
        photo_urls: list[str] = []
        seen: set[str] = set()

        def _add(url: str) -> None:
            # Unescape HTML entities (e.g. &amp; -> &)
            clean = url.replace("&amp;", "&")
            if not clean.startswith("http"):
                clean = f"{self.BASE_URL}{clean}"
            # Deduplicate by media ID (the 'id' param)
            id_match = re.search(r"[?&]id=([^&]+)", clean)
            dedup_key = id_match.group(1) if id_match else clean
            if dedup_key not in seen:
                seen.add(dedup_key)
                photo_urls.append(clean)

        # Strategy 1: Gallery/carousel container images
        for selector in [
            "div.primary-photo-container img",
            "div.photo-gallery img",
            "div.slideshow img",
            "div[class*='photo'] img",
            "div[class*='gallery'] img",
            "div[class*='carousel'] img",
        ]:
            for img in soup.select(selector):
                url = img.get("data-src") or img.get("src") or ""
                if url and ("centris.ca" in url or "media.ashx" in url):
                    _add(url)

        # Strategy 2: All images with Centris media URLs (always run)
        media_re = re.compile(r"centris\.ca/media|media\.ashx", re.I)
        for img in soup.find_all("img"):
            for attr in ("src", "data-src"):
                url = img.get(attr, "")
                if url and media_re.search(url):
                    _add(url)

        # Strategy 3: JSON/JS embedded photo arrays (always run)
        for script in soup.find_all("script"):
            text = script.string or ""
            urls = re.findall(
                r'"(https?://[^"]*centris\.ca/media\.ashx[^"]*)"',
                text,
            )
            for url in urls:
                _add(url)

        # Filter: keep only actual photos (t=pi), not thumbnails (t=b, t=c)
        photos_only = [u for u in photo_urls if "t=pi" in u]
        return photos_only if photos_only else photo_urls

    def _parse_characteristics(self, soup: BeautifulSoup) -> dict[str, str]:
        """Parse all carac-container sections into a dict.

        Centris detail pages have structured data in .carac-container divs
        with .carac-title and .carac-value children.
        """
        characteristics = {}

        for container in soup.find_all(class_="carac-container"):
            title_elem = container.find(class_="carac-title")
            value_elem = container.find(class_="carac-value")

            if title_elem:
                title = title_elem.get_text(strip=True)
                if value_elem:
                    value = value_elem.get_text(" ", strip=True)
                else:
                    # Some just have title with text after
                    text = container.get_text(" ", strip=True)
                    value = text.replace(title, "").strip()

                if value:
                    characteristics[title] = value

        return characteristics

    async def get_listing_details(
        self, listing_id: str, url: Optional[str] = None
    ) -> Optional[PropertyListing]:
        """Get full details for a single listing.

        Fetches the individual listing page and extracts comprehensive data
        including square footage, lot size, year built, taxes, assessment,
        gross revenue, and other details not available in search results.

        Args:
            listing_id: The Centris listing ID (e.g., "centris-12345678")
            url: Optional full URL to the listing detail page

        Returns:
            PropertyListing with full details, or None if not found
        """
        # Extract numeric ID
        match = re.search(r"centris-(\d+)", listing_id)
        if not match:
            logger.warning(f"Invalid listing ID format: {listing_id}")
            return None

        centris_id = match.group(1)

        # Use provided URL or search for the listing
        if not url:
            url = f"{self.BASE_URL}/en/{centris_id}"

        try:
            # Try Playwright first for JS-rendered content (gallery photos)
            html = None
            if os.environ.get("PLAYWRIGHT_ENABLED", "false").lower() in (
                "true", "1", "yes",
            ):
                await self._rate_limit()
                html = await self._get_page_with_browser(url)
                if html:
                    logger.debug(f"Playwright rendered {listing_id}")

            if html:
                soup = BeautifulSoup(html, "html.parser")
            else:
                response = await self._make_request(url)
                # Detect delisted listings: Centris returns 302 → search results
                # page (HTTP 200) with "listingnotfound" in the final URL.
                final_url = str(response.url)
                if "listingnotfound" in final_url:
                    logger.info(f"Listing {listing_id} is delisted (redirected to search)")
                    return None
                # Use response.text (httpx auto-decodes from Content-Type header)
                # to correctly handle ½ and other special characters
                soup = BeautifulSoup(response.text, "html.parser")

            page_text = soup.get_text(" ", strip=True)

            # Detect search results page (fallback for redirects we didn't catch above)
            # A detail page has carac-container divs; a search results page has
            # property-thumbnail-item divs but no characteristics.
            has_characteristics = bool(soup.find(class_="carac-container"))
            has_search_results = bool(soup.find(class_="property-thumbnail-item"))
            if not has_characteristics and has_search_results:
                logger.info(f"Listing {listing_id} returned search results page, not detail page")
                return None

            # Parse structured characteristics
            chars = self._parse_characteristics(soup)

            # === PRICE ===
            price = 0
            price_meta = soup.find("meta", itemprop="price")
            if price_meta:
                price = self._parse_price(price_meta.get("content", "")) or 0
            if not price:
                price_elem = soup.find(class_="price")
                if price_elem:
                    price = self._parse_price(price_elem.get_text(strip=True)) or 0

            # === ADDRESS & LOCATION ===
            address = "Unknown"
            city = "Montreal"
            postal_code = None

            # Try schema.org FIRST (most reliable source)
            addr_elem = soup.find("span", itemprop="streetAddress")
            if addr_elem:
                address = addr_elem.get_text(strip=True)
            city_elem = soup.find("span", itemprop="addressLocality")
            if city_elem:
                city = city_elem.get_text(strip=True)
            postal_elem = soup.find("span", itemprop="postalCode")
            if postal_elem:
                postal_code = postal_elem.get_text(strip=True)

            # Fallback: regex search for Canadian postal code in page text
            if not postal_code:
                pc_match = re.search(
                    r"\b([A-Za-z]\d[A-Za-z])\s?(\d[A-Za-z]\d)\b", page_text
                )
                if pc_match:
                    postal_code = (
                        f"{pc_match.group(1).upper()} {pc_match.group(2).upper()}"
                    )

            # Fallback to title parsing if schema.org didn't have address
            if address == "Unknown":
                title = soup.find("title")
                if title:
                    title_text = title.get_text(strip=True)
                    # Title format varies:
                    # "5plex for sale in La Malbaie, 925 - 975, boul. De Comporté, MLS# - Centris.ca"
                    # "House for sale in City, 123, Rue Example, MLS# - Centris.ca"
                    parts = title_text.split(",")
                    for i, part in enumerate(parts):
                        part = part.strip()
                        # Street address usually has a number at the start
                        if re.match(r"^\d+", part):
                            # Collect number + subsequent street name parts until MLS#
                            addr_parts = [part]
                            for k in range(i + 1, len(parts)):
                                next_part = parts[k].strip()
                                if re.search(r"MLS|Centris|centris", next_part, re.I):
                                    break
                                addr_parts.append(next_part)
                            address = ", ".join(addr_parts)
                            # City is usually the part after "in" before the address
                            if i >= 1 and city == "Montreal":
                                for j in range(i - 1, -1, -1):
                                    prev_part = parts[j].strip()
                                    if "in " in prev_part:
                                        city = prev_part.split("in ")[-1].strip()
                                        break
                                    elif j == i - 1:
                                        city = prev_part
                            break

            # === BEDROOMS & BATHROOMS ===
            bedrooms = 0
            bathrooms = 0.0
            rooms = 0

            # Try teaser section first (single-family properties)
            teaser = soup.find(class_="teaser")
            if teaser:
                cac = teaser.find(class_="cac")
                if cac:
                    m = re.search(r"(\d+)", cac.get_text())
                    if m:
                        bedrooms = int(m.group(1))
                sdb = teaser.find(class_="sdb")
                if sdb:
                    m = re.search(r"(\d+(?:\.\d+)?)", sdb.get_text())
                    if m:
                        bathrooms = float(m.group(1))
                piece = teaser.find(class_="piece")
                if piece:
                    m = re.search(r"(\d+)", piece.get_text())
                    if m:
                        rooms = int(m.group(1))

            # For multi-family, try "Main unit" characteristic (EN/FR)
            main_unit_text = None
            for key in ("Main unit", "Unité principale", "Logement principal"):
                if key in chars:
                    main_unit_text = chars[key]
                    break
            if bedrooms == 0 and main_unit_text:
                # Format EN: "4 rooms, 2 bedrooms, 1 bathroom"
                # Format FR: "4 pièces, 2 chambres, 1 salle de bain"
                bed_match = re.search(r"(\d+)\s*(?:bedroom|chambre)", main_unit_text, re.I)
                if bed_match:
                    bedrooms = int(bed_match.group(1))
                bath_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:bathroom|salle de bain|sdb)", main_unit_text, re.I)
                if bath_match:
                    bathrooms = float(bath_match.group(1))
                room_match = re.search(r"(\d+)\s*(?:room|pièce)", main_unit_text, re.I)
                if room_match:
                    rooms = int(room_match.group(1))

            # === PROPERTY CHARACTERISTICS ===
            # Units: sqft, pi (pieds), pc (pieds carrés), mc (mètres carrés)
            _AREA_UNITS = r"(?:sqft|pi\b|pc\b|sq\.?\s*ft)"
            def _parse_area(text: str) -> int | None:
                """Parse an area value, handling comma and space separators."""
                cleaned = re.sub(r"[^\d]", "", text)
                return int(cleaned) if cleaned else None

            # Living area / Building area
            sqft = None
            sqft_match = re.search(
                r"(?:Living area|Building area|Superficie habitable|Superficie du bâtiment)[:\s]*([\d,.\s]+)\s*" + _AREA_UNITS,
                page_text, re.I
            )
            if sqft_match:
                sqft = _parse_area(sqft_match.group(1))

            # Lot area (from characteristics or text, EN/FR)
            lot_sqft = None
            for key in ("Lot area", "Superficie du terrain", "Terrain"):
                if key in chars:
                    lot_match = re.search(r"([\d,.\s]+)\s*" + _AREA_UNITS, chars[key])
                    if lot_match:
                        lot_sqft = _parse_area(lot_match.group(1))
                    break
            if not lot_sqft:
                lot_match = re.search(r"(?:Lot area|Superficie du terrain)[:\s]*([\d,.\s]+)\s*" + _AREA_UNITS, page_text, re.I)
                if lot_match:
                    lot_sqft = _parse_area(lot_match.group(1))

            # Year built (EN/FR)
            year_built = None
            for key in ("Year built", "Année de construction"):
                if key in chars:
                    m = re.search(r"(\d{4})", chars[key])
                    if m:
                        year_built = int(m.group(1))
                    break

            # Building style (EN/FR)
            building_style = chars.get("Building style", chars.get("Style du bâtiment", ""))

            # === UNITS (for multi-family) ===
            units = 1
            url_lower = url.lower()
            if "duplex" in url_lower:
                units = 2
            elif "triplex" in url_lower:
                units = 3
            elif "quadruplex" in url_lower:
                units = 4
            elif "quintuplex" in url_lower or "5-plex" in url_lower:
                units = 5

            # Override from characteristics if available (EN/FR)
            for key in ("Number of units", "Nombre d'unités", "Nombre de logements"):
                if key in chars:
                    m = re.search(r"(\d+)", chars[key])
                    if m:
                        units = int(m.group(1))
                    break

            # === INCOME & EXPENSES (for investment properties) ===
            gross_revenue = None
            total_expenses = None
            net_income = None

            def _parse_amount(text: str) -> int | None:
                """Parse a dollar amount string, handling French/English formats.

                Handles:
                  - "123,456"     → 123456  (EN thousands comma)
                  - "123 456"     → 123456  (FR thousands space)
                  - "123 456,78"  → 123456  (FR with decimals — truncate cents)
                  - "123,456.78"  → 123456  (EN with decimals)
                  - "$123 456"    → 123456  (with currency symbol)
                """
                if not text:
                    return None
                # Strip currency symbols and surrounding whitespace
                cleaned = re.sub(r"[$€\s]", "", text.strip())
                if not cleaned:
                    return None
                # If there's a decimal separator (last comma or dot with ≤2 digits after),
                # split there and keep only the integer part
                decimal_match = re.match(r"^([\d,.\s]+?)[.,](\d{1,2})$", cleaned)
                if decimal_match:
                    cleaned = decimal_match.group(1)
                # Remove remaining thousands separators (commas, dots, spaces)
                cleaned = re.sub(r"[,.\s]", "", cleaned)
                return int(cleaned) if cleaned.isdigit() else None

            for key in ("Potential gross revenue", "Gross revenue",
                        "Revenus bruts potentiels", "Revenu brut potentiel",
                        "Revenus bruts", "Revenu brut"):
                if key in chars:
                    gross_revenue = _parse_amount(chars[key])
                    break

            # Centris may show total expenses and/or net income for revenue properties
            for key in ("Total expenses", "Expenses", "Operating expenses",
                        "Dépenses totales", "Dépenses", "Dépenses d'exploitation"):
                if key in chars:
                    total_expenses = _parse_amount(chars[key])
                    break

            for key in ("Net income", "Estimated net income",
                        "Revenu net", "Revenu net estimé"):
                if key in chars:
                    net_income = _parse_amount(chars[key])
                    break

            # Validate financial fields independently before inference
            # Reject nonsensical values: negative, zero, or implausibly high
            _finance_inferred: list[str] = []

            def _validate_financial(val: int | None, name: str) -> int | None:
                if val is None:
                    return None
                if val <= 0:
                    logger.debug(f"Rejecting {name}={val} (non-positive) for {listing_id}")
                    return None
                if val > 10_000_000:  # >$10M annual is implausible for residential
                    logger.debug(f"Rejecting {name}={val} (>$10M) for {listing_id}")
                    return None
                return val

            gross_revenue = _validate_financial(gross_revenue, "gross_revenue")
            total_expenses = _validate_financial(total_expenses, "total_expenses")
            net_income = _validate_financial(net_income, "net_income")

            # Cross-check: expenses should not exceed revenue
            if gross_revenue and total_expenses and total_expenses > gross_revenue:
                logger.warning(
                    f"Expenses ({total_expenses}) > revenue ({gross_revenue}) for {listing_id}, "
                    f"clearing expenses"
                )
                total_expenses = None

            # Infer missing values when two of the three are known, and flag inferred fields
            if gross_revenue and total_expenses and not net_income:
                net_income = gross_revenue - total_expenses
                if net_income > 0:
                    _finance_inferred.append("net_income")
                else:
                    net_income = None  # Don't store negative inferred net income
            elif gross_revenue and net_income and not total_expenses:
                total_expenses = gross_revenue - net_income
                if total_expenses > 0:
                    _finance_inferred.append("total_expenses")
                else:
                    total_expenses = None
            elif not gross_revenue and total_expenses and net_income:
                gross_revenue = total_expenses + net_income
                _finance_inferred.append("gross_revenue")

            # === TAXES & ASSESSMENT ===
            municipal_assessment = None
            annual_taxes = None

            # Assessment - look for "Total $xxx,xxx" pattern (EN/FR)
            assess_match = re.search(
                r"(?:Municipal assessment|Évaluation municipale).*?Total\s*\$?([\d,\s]+)",
                page_text, re.I | re.S
            )
            if assess_match:
                municipal_assessment = _parse_amount(assess_match.group(1))

            # Taxes - find the second occurrence (first is filter UI) (EN/FR)
            tax_matches = re.findall(
                r"(?:Taxes|Taxes)\s*(?:Municipal|Municipale).*?\$?([\d,\s]+)\s*(?:School|Scolaire).*?\$?([\d,\s]+)\s*Total\s*\$?([\d,\s]+)",
                page_text, re.I
            )
            if len(tax_matches) >= 2:
                annual_taxes = _parse_amount(tax_matches[1][2])

            # === PARKING ===
            parking_spaces = 0
            garage_spaces = 0
            if "Parking (total)" in chars:
                parking_text = chars["Parking (total)"]
                # Parse "Driveway (1)" or "Garage (2), Driveway (1)"
                p_match = re.search(r"\((\d+)\)", parking_text)
                if p_match:
                    parking_spaces = int(p_match.group(1))
                g_match = re.search(r"[Gg]arage.*?\((\d+)\)", parking_text)
                if g_match:
                    garage_spaces = int(g_match.group(1))

            # === PROPERTY TYPE ===
            # Check title first (more reliable than URL)
            type_text = ""
            title_lower = title.get_text().lower() if title else ""
            check_text = title_lower + " " + url_lower

            if "triplex" in check_text:
                type_text = "triplex"
            elif "duplex" in check_text:
                type_text = "duplex"
            elif "quadruplex" in check_text:
                type_text = "quadruplex"
            elif "quintuplex" in check_text or "5-plex" in check_text:
                type_text = "multiplex"
            elif "condo" in check_text:
                type_text = "house"
            elif "house" in check_text:
                type_text = "house"

            property_type = self._determine_property_type(type_text, units)

            # P0 fix: Ensure unit count is consistent with property type on detail pages
            _TYPE_MIN_UNITS = {
                PropertyType.DUPLEX: 2,
                PropertyType.TRIPLEX: 3,
                PropertyType.QUADPLEX: 4,
                PropertyType.MULTIPLEX: 5,
            }
            min_units = _TYPE_MIN_UNITS.get(property_type)
            if min_units and units < min_units:
                units = min_units

            # === PHOTOS ===
            photo_urls = self._extract_photo_urls(soup)

            # === BUILD RAW DATA with all extra info ===
            raw_data = {
                "centris_id": centris_id,
                "rooms": rooms,
                "building_style": building_style,
                "parking_spaces": parking_spaces,
                "garage_spaces": garage_spaces,
                "photo_urls": photo_urls,
                "finance_inferred_fields": _finance_inferred if _finance_inferred else None,
            }

            # Add all characteristics
            for key, value in chars.items():
                snake_key = key.lower().replace(" ", "_").replace("(", "").replace(")", "")
                if snake_key not in raw_data:
                    raw_data[snake_key] = value

            return PropertyListing(
                id=listing_id,
                source=self.name,
                address=address,
                city=city,
                postal_code=postal_code,
                price=price,
                property_type=property_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                sqft=sqft,
                lot_sqft=lot_sqft,
                year_built=year_built,
                units=units,
                estimated_rent=None,
                gross_revenue=gross_revenue,
                total_expenses=total_expenses,
                net_income=net_income,
                municipal_assessment=municipal_assessment,
                annual_taxes=annual_taxes,
                photo_urls=photo_urls,
                listing_date=date.today(),
                url=url,
                raw_data=raw_data,
            )

        except (CaptchaError, RateLimitError):
            raise
        except Exception as e:
            logger.error(f"Error fetching listing details for {listing_id}: {e}", exc_info=True)
            return None

    async def enrich_listing(
        self, listing: PropertyListing
    ) -> PropertyListing:
        """Enrich a search result listing with detail page data.

        Fetches the detail page for a listing and merges additional data
        (sqft, lot_sqft, year_built, postal_code) into the existing listing.

        Args:
            listing: A PropertyListing from search results

        Returns:
            The same listing with additional fields populated
        """
        if not listing.url or listing.url == self.SEARCH_URL:
            return listing

        try:
            detailed = await self.get_listing_details(listing.id, url=listing.url)
            if detailed:
                # Merge detail data into original listing
                # Keep original values where detail is missing
                return PropertyListing(
                    id=listing.id,
                    source=listing.source,
                    address=listing.address,
                    city=listing.city,
                    postal_code=detailed.postal_code or listing.postal_code,
                    price=listing.price,  # Keep original price
                    property_type=listing.property_type,
                    bedrooms=listing.bedrooms or detailed.bedrooms,
                    bathrooms=listing.bathrooms or detailed.bathrooms,
                    sqft=detailed.sqft or listing.sqft,
                    lot_sqft=detailed.lot_sqft or listing.lot_sqft,
                    year_built=detailed.year_built or listing.year_built,
                    units=listing.units,
                    estimated_rent=listing.estimated_rent,
                    gross_revenue=detailed.gross_revenue or listing.gross_revenue,
                    total_expenses=detailed.total_expenses or listing.total_expenses,
                    net_income=detailed.net_income or listing.net_income,
                    municipal_assessment=detailed.municipal_assessment or listing.municipal_assessment,
                    annual_taxes=detailed.annual_taxes or listing.annual_taxes,
                    photo_urls=detailed.photo_urls or listing.photo_urls,
                    listing_date=listing.listing_date,
                    url=listing.url,
                    raw_data={
                        **(listing.raw_data or {}),
                        **(detailed.raw_data or {}),
                        "enriched": True,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to enrich listing {listing.id}: {e}")

        return listing

    async def fetch_listings_with_details(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[PropertyListing]:
        """Fetch listings and enrich each with detail page data.

        This is slower than fetch_listings but provides complete data
        including square footage, lot size, and year built.

        Args:
            region: Geographic region
            property_types: Filter by property types
            min_price: Minimum price
            max_price: Maximum price
            limit: Maximum listings to return

        Returns:
            List of fully enriched PropertyListing objects
        """
        # First get search results
        listings = await self.fetch_listings(
            region=region,
            property_types=property_types,
            min_price=min_price,
            max_price=max_price,
            limit=limit,
        )

        # Enrich each listing with detail page data
        enriched = []
        for listing in listings:
            enriched_listing = await self.enrich_listing(listing)
            enriched.append(enriched_listing)
            logger.debug(f"Enriched listing {listing.id}")

        return enriched

    async def _fetch_by_type_url(
        self,
        property_type: str,
        region: str,
    ) -> list[PropertyListing]:
        """Fetch listings using a property-type specific URL.

        Centris has different URL patterns for each property type that return
        different result sets (e.g., /en/duplexes~for-sale~montreal-island).

        Args:
            property_type: Property type key (DUPLEX, TRIPLEX, etc.)
            region: Region key (montreal, laval, etc.)

        Returns:
            List of PropertyListing objects from this type-specific search
        """
        url_pattern = PROPERTY_TYPE_URLS.get(property_type)
        if not url_pattern:
            logger.warning(f"No URL pattern for type: {property_type}")
            return []

        region_slug = REGION_URL_MAPPING.get(region.lower(), region)
        url = f"{self.BASE_URL}{url_pattern.format(region=region_slug)}"

        try:
            response = await self._make_request(url)
            soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")

            listings = []
            cards = soup.select("div.property-thumbnail-item")

            seen_ids = set()
            for card in cards:
                listing = self._parse_listing_card(card)
                if listing and listing.id not in seen_ids:
                    seen_ids.add(listing.id)
                    listings.append(listing)

            return listings

        except Exception as e:
            logger.error(f"Error fetching {property_type} listings: {e}")
            return []

    async def fetch_listings_multi_type(
        self,
        region: str = "montreal",
        property_types: Optional[list[str]] = None,
        enrich: bool = False,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        max_pages: int = 10,
    ) -> list[PropertyListing]:
        """Fetch listings across multiple property types with full pagination.

        Uses AJAX pagination (via fetch_all_listings) for each property-type
        URL to retrieve all results, not just the first page.

        Args:
            region: Geographic region (e.g., "montreal", "south-shore")
            property_types: Types to search. Defaults to all multi-family
                           (DUPLEX, TRIPLEX, QUADPLEX, MULTIPLEX)
            enrich: If True, fetch detail page for each listing (slower)
            min_price: Optional minimum price filter (applied client-side)
            max_price: Optional maximum price filter (applied client-side)
            max_pages: Max pages per type/slug combo (default 10 = ~200 listings)

        Returns:
            Deduplicated list of PropertyListing objects from all types

        Example:
            listings = await scraper.fetch_listings_multi_type(
                region="south-shore",
                property_types=["DUPLEX", "TRIPLEX", "QUADPLEX"],
                min_price=400000,
                max_price=1000000,
            )
        """
        if property_types is None:
            property_types = ["DUPLEX", "TRIPLEX", "ALL_PLEX"]

        # Map types without dedicated URLs to ALL_PLEX
        search_types = []
        for t in property_types:
            if t in ("QUADPLEX", "MULTIPLEX"):
                if "ALL_PLEX" not in search_types:
                    search_types.append("ALL_PLEX")
            else:
                if t not in search_types:
                    search_types.append(t)

        region_key = region.lower()
        slug = REGION_URL_MAPPING.get(region_key, region_key)

        all_listings: dict[str, PropertyListing] = {}

        for prop_type in search_types:
            url_pattern = PROPERTY_TYPE_URLS.get(prop_type)
            if not url_pattern:
                continue

            search_url = f"{self.BASE_URL}{url_pattern.format(region=slug)}"
            logger.info(f"Searching {prop_type} in {slug}...")

            try:
                type_listings = await self.fetch_all_listings(
                    search_url=search_url,
                    enrich=False,
                    min_price=min_price,
                    max_price=max_price,
                    max_pages=max_pages,
                )

                new_count = 0
                for listing in type_listings:
                    if listing.id not in all_listings:
                        all_listings[listing.id] = listing
                        new_count += 1

                logger.info(
                    f"{prop_type}/{slug}: {len(type_listings)} found, "
                    f"{new_count} new unique"
                )

            except (CaptchaError, RateLimitError) as e:
                logger.warning(f"Search stopped due to: {e}")
                break
            except Exception as e:
                logger.error(f"Error searching {prop_type}/{slug}: {e}")

        logger.info(
            f"Multi-type search complete: {len(search_types)} types, "
            f"{len(all_listings)} unique listings"
        )

        result = list(all_listings.values())

        if enrich:
            logger.info(f"Enriching {len(result)} listings with detail data...")
            enriched = []
            for i, listing in enumerate(result):
                enriched_listing = await self.enrich_listing(listing)
                enriched.append(enriched_listing)
                if (i + 1) % 10 == 0:
                    logger.info(f"Enriched {i + 1}/{len(result)} listings")
            return enriched

        return result

    async def fetch_listings_multi_band(
        self,
        region: str,
        property_types: Optional[list[str]] = None,
        min_price: int = 300000,
        max_price: int = 1500000,
        band_size: int = 200000,
        enrich: bool = False,
        limit_per_band: Optional[int] = None,
    ) -> list[PropertyListing]:
        """Fetch listings across multiple price bands for more results.

        NOTE: Centris ignores URL-based price parameters. This method now
        delegates to fetch_listings_multi_type() which uses property-type
        specific URLs and applies price filters client-side.

        For more listings, use fetch_listings_multi_type() directly.

        Args:
            region: Geographic region (e.g., "montreal", "laval")
            property_types: Filter by types (e.g., ["DUPLEX", "TRIPLEX"])
            min_price: Minimum price (applied client-side)
            max_price: Maximum price (applied client-side)
            band_size: Ignored (kept for API compatibility)
            enrich: If True, fetch detail page for each listing (slower)
            limit_per_band: Ignored (kept for API compatibility)

        Returns:
            Deduplicated list of PropertyListing objects
        """
        # Delegate to the more effective multi-type approach
        return await self.fetch_listings_multi_type(
            region=region,
            property_types=property_types,
            enrich=enrich,
            min_price=min_price,
            max_price=max_price,
        )

    async def fetch_all_listings(
        self,
        search_url: str,
        enrich: bool = False,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        max_pages: int = 20,
    ) -> list[PropertyListing]:
        """Fetch ALL listings from a search URL using AJAX pagination.

        This method uses Centris's internal pagination API to retrieve all
        results, not just the first 20. It works by:
        1. Getting the first page via GET request
        2. Calling /Property/GetInscriptions with startPosition for subsequent pages

        Args:
            search_url: Full Centris search URL
                       (e.g., "https://www.centris.ca/en/plexes~for-sale~montreal-south-shore")
            enrich: If True, fetch detail page for each listing (slower)
            min_price: Optional minimum price filter (applied client-side)
            max_price: Optional maximum price filter (applied client-side)
            max_pages: Maximum pages to fetch (default 20 = 400 listings)

        Returns:
            List of all PropertyListing objects from the search

        Example:
            # Get all ~229 plex listings on South Shore
            listings = await scraper.fetch_all_listings(
                "https://www.centris.ca/en/plexes~for-sale~montreal-south-shore",
                min_price=400000,
                max_price=1000000,
            )
        """
        client = await self._get_client()
        all_listings: dict[str, PropertyListing] = {}
        page = 1

        # Fetch first page
        try:
            await self._rate_limit()
            response = await client.get(search_url)

            if response.status_code != 200:
                logger.error(f"Initial page failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")
            cards = soup.select("div.property-thumbnail-item")

            for card in cards:
                listing = self._parse_listing_card(card)
                if listing and listing.id not in all_listings:
                    all_listings[listing.id] = listing

            logger.info(f"Page 1: {len(cards)} cards, {len(all_listings)} unique")

            if len(cards) == 0:
                return []

        except Exception as e:
            logger.error(f"Error fetching first page: {e}")
            return []

        # Paginate using AJAX API
        api_url = f"{self.BASE_URL}/Property/GetInscriptions"

        for page in range(2, max_pages + 1):
            start_pos = (page - 1) * 20

            try:
                await self._rate_limit()

                # AJAX request requires specific headers
                response = await client.post(
                    api_url,
                    json={"startPosition": start_pos},
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "Content-Type": "application/json",
                    },
                )

                if response.status_code != 200:
                    logger.warning(f"Page {page} failed: {response.status_code}")
                    break

                data = response.json()
                html = data.get("d", {}).get("Result", {}).get("html", "")

                if not html:
                    logger.info(f"No more results after page {page - 1}")
                    break

                soup = BeautifulSoup(html, "html.parser")
                cards = soup.select("div.property-thumbnail-item")

                if not cards:
                    break

                new_count = 0
                for card in cards:
                    listing = self._parse_listing_card(card)
                    if listing and listing.id not in all_listings:
                        all_listings[listing.id] = listing
                        new_count += 1

                logger.info(
                    f"Page {page}: {len(cards)} cards, {new_count} new "
                    f"(total: {len(all_listings)})"
                )

                # If we got less than 20, we're on the last page
                if len(cards) < 20:
                    break

            except (CaptchaError, RateLimitError):
                raise
            except Exception as e:
                logger.error(f"Error on page {page}: {e}")
                break

        logger.info(f"Pagination complete: {len(all_listings)} total listings")

        # Apply price filters
        result = list(all_listings.values())
        if min_price:
            result = [l for l in result if l.price >= min_price]
        if max_price:
            result = [l for l in result if l.price <= max_price]

        logger.info(f"After price filter: {len(result)} listings")

        # Optionally enrich
        if enrich:
            logger.info(f"Enriching {len(result)} listings...")
            enriched = []
            for i, listing in enumerate(result):
                enriched_listing = await self.enrich_listing(listing)
                enriched.append(enriched_listing)
                if (i + 1) % 20 == 0:
                    logger.info(f"Enriched {i + 1}/{len(result)}")
            return enriched

        return result

    def is_available(self) -> bool:
        """Check if Centris scraper is available.

        The scraper is always "available" since it doesn't require API keys,
        but actual scraping may fail due to CAPTCHAs or rate limits.

        Returns:
            True (scraping doesn't require credentials)
        """
        return True

    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "CentrisScraper":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
