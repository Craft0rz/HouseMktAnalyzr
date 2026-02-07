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
    "longueuil": "Longueuil",
    "south-shore": "South Shore",
    "north-shore": "North Shore",
    "laurentides": "Laurentides",
    "lanaudiere": "Lanaudière",
}

# Mapping of property types to Centris property type codes
PROPERTY_TYPE_MAPPING = {
    "HOUSE": ["Detached", "Bungalow", "Cottage", "Two or more storeys"],
    "DUPLEX": ["Duplex"],
    "TRIPLEX": ["Triplex"],
    "QUADPLEX": ["Quadruplex"],
    "MULTIPLEX": ["Quintuplex or more", "Multi-family (5+)"],
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
            "Chrome/120.0.0.0 Safari/537.36"
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
                    "Connection": "keep-alive",
                },
                follow_redirects=True,
            )
        return self._client

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
        """
        content = response.text.lower()

        # If we see property listings, it's not a CAPTCHA page
        if "property-thumbnail-item" in content or "property-thumbnail-summary" in content:
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

        Args:
            card: BeautifulSoup element containing the listing card

        Returns:
            PropertyListing or None if parsing fails
        """
        try:
            # Extract URL
            link = card.find("a", class_="property-thumbnail-summary-link")
            if not link:
                link = card.find("a", href=re.compile(r"/en/"))
            url = link.get("href", "") if link else ""
            if url and not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            # Extract address
            address_elem = card.find(class_=re.compile(r"address|location"))
            address_text = address_elem.get_text(strip=True) if address_elem else ""

            # Try alternative address extraction
            if not address_text:
                address_parts = card.find_all(class_=re.compile(r"street|city"))
                address_text = ", ".join(p.get_text(strip=True) for p in address_parts)

            # Extract city from address
            city = "Montreal"  # Default
            if "," in address_text:
                parts = address_text.split(",")
                city = parts[-1].strip() if len(parts) > 1 else city

            # Extract price
            price_elem = card.find(class_=re.compile(r"price"))
            price_text = price_elem.get_text(strip=True) if price_elem else ""
            price = self._parse_price(price_text)

            if not price:
                return None  # Skip listings without price

            # Extract property details
            details_text = card.get_text(" ", strip=True)

            bedrooms = self._parse_bedrooms(details_text)
            bathrooms = self._parse_bathrooms(details_text)
            sqft = self._parse_sqft(details_text)

            # Determine property type
            type_elem = card.find(class_=re.compile(r"category|type"))
            type_text = type_elem.get_text(strip=True) if type_elem else ""

            # Count units for multi-family
            units = 1
            unit_match = re.search(r"(\d+)\s*(?:unit|logement)", details_text, re.IGNORECASE)
            if unit_match:
                units = int(unit_match.group(1))
            elif "duplex" in type_text.lower():
                units = 2
            elif "triplex" in type_text.lower():
                units = 3
            elif "quadruplex" in type_text.lower():
                units = 4

            property_type = self._determine_property_type(type_text, units)

            # Generate ID
            listing_id = self._generate_listing_id(url, address_text)

            return PropertyListing(
                id=listing_id,
                source=self.name,
                address=address_text or "Unknown",
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
                raw_data={"source_html": str(card)[:500]},  # Truncate for storage
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
            soup = BeautifulSoup(response.text, "html.parser")

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

            for card in cards:
                listing = self._parse_listing_card(card)
                if listing:
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
        all_listings: list[PropertyListing] = []
        page = 1
        max_pages = 10  # Safety limit

        logger.info(
            f"Fetching Centris listings: region={region}, "
            f"types={property_types}, price={min_price}-{max_price}"
        )

        while len(all_listings) < limit and page <= max_pages:
            page_listings = await self._fetch_search_page(
                region=region,
                property_types=property_types,
                min_price=min_price,
                max_price=max_price,
                page=page,
            )

            if not page_listings:
                break  # No more results

            all_listings.extend(page_listings)
            page += 1

        # Apply limit
        result = all_listings[:limit]
        logger.info(f"Found {len(result)} listings from Centris")

        return result

    async def get_listing_details(
        self, listing_id: str
    ) -> Optional[PropertyListing]:
        """Get full details for a single listing.

        Args:
            listing_id: The Centris listing ID (e.g., "centris-12345678")

        Returns:
            PropertyListing with full details, or None if not found
        """
        # Extract numeric ID
        match = re.search(r"centris-(\d+)", listing_id)
        if not match:
            return None

        centris_id = match.group(1)
        url = f"{self.BASE_URL}/en/{centris_id}"

        try:
            response = await self._make_request(url)
            soup = BeautifulSoup(response.text, "html.parser")

            # Parse detailed listing page
            # This would need more specific parsing for the detail page
            # For now, return a basic listing

            # Extract address
            address_elem = soup.find("h1", class_=re.compile(r"address"))
            if not address_elem:
                address_elem = soup.find("span", itemprop="streetAddress")
            address = address_elem.get_text(strip=True) if address_elem else "Unknown"

            # Extract price
            price_elem = soup.find(class_=re.compile(r"price"))
            price_text = price_elem.get_text(strip=True) if price_elem else "0"
            price = self._parse_price(price_text) or 0

            # Extract city
            city_elem = soup.find("span", itemprop="addressLocality")
            city = city_elem.get_text(strip=True) if city_elem else "Montreal"

            # Extract full details
            details_text = soup.get_text(" ", strip=True)

            return PropertyListing(
                id=listing_id,
                source=self.name,
                address=address,
                city=city,
                postal_code=None,
                price=price,
                property_type=PropertyType.HOUSE,  # Would need better detection
                bedrooms=self._parse_bedrooms(details_text),
                bathrooms=self._parse_bathrooms(details_text),
                sqft=self._parse_sqft(details_text),
                lot_sqft=None,
                year_built=None,
                units=1,
                estimated_rent=None,
                listing_date=date.today(),
                url=url,
                raw_data=None,
            )

        except Exception as e:
            logger.error(f"Error fetching listing details: {e}")
            return None

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
