"""Walk Score scraper with Nominatim geocoding.

Fetches walk/transit/bike scores from walkscore.com by scraping
the public score page. No API key required.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WALKSCORE_BASE = "https://www.walkscore.com/score"


@dataclass
class WalkScoreResult:
    walk_score: int | None
    transit_score: int | None
    bike_score: int | None
    latitude: float
    longitude: float


async def geocode_address(
    address: str,
    city: str,
    client: httpx.AsyncClient,
) -> Optional[tuple[float, float]]:
    """Geocode an address using Nominatim (OpenStreetMap).

    Returns (latitude, longitude) or None if geocoding fails.
    """
    query = f"{address}, {city}, QC, Canada"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "ca",
    }
    headers = {"User-Agent": "HouseMktAnalyzr/1.0"}

    try:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            logger.warning(f"Geocoding returned no results for: {query}")
            return None

        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.error(f"Geocoding failed for {query}: {e}")
        return None


def _build_walkscore_slug(address: str, city: str) -> str:
    """Build a URL slug for walkscore.com from address and city.

    Handles Centris-style addresses like "3878 - 3882, Rue La Fontaine"
    and city names like "Montréal (Mercier/Hochelaga-Maisonneuve)".

    Example: "3878 - 3882, Rue La Fontaine", "Montréal (Mercier/Hochelaga-Maisonneuve)"
          -> "3878-rue-la-fontaine-montreal-qc"
    """
    # For multi-number addresses (3878 - 3882), just use the first number
    addr = re.sub(r"(\d+)\s*-\s*\d+", r"\1", address)
    # Strip borough/neighborhood in parentheses from city
    clean_city = re.sub(r"\s*\(.*?\)", "", city)
    # Fix double-encoded UTF-8 (Ã© -> é) before accent removal
    text = f"{addr} {clean_city} QC"
    try:
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    # Remove accents (basic: é->e, è->e, ê->e, à->a, etc.)
    for src, dst in [("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
                     ("à", "a"), ("â", "a"), ("ô", "o"), ("î", "i"),
                     ("ù", "u"), ("û", "u"), ("ç", "c")]:
        text = text.replace(src, dst).replace(src.upper(), dst.upper())
    # Remove non-alphanumeric (keep spaces and hyphens)
    slug = re.sub(r"[^\w\s-]", "", text)
    # Collapse multiple spaces/hyphens into single hyphen
    slug = re.sub(r"[\s-]+", "-", slug.strip())
    return slug.lower()


def _extract_score(soup: BeautifulSoup, score_type: str) -> int | None:
    """Extract a score from Walk Score page HTML.

    Looks for badge images matching: //pp.walk.sc/badge/{score_type}/score/{N}.svg
    """
    pattern = re.compile(rf"pp\.walk\.sc/badge/{score_type}/score/(\d+)\.svg")
    img = soup.find("img", src=pattern)
    if img:
        match = pattern.search(img["src"])
        if match:
            return int(match.group(1))
    return None


async def scrape_walk_score(
    address: str,
    city: str,
    client: httpx.AsyncClient,
) -> Optional[dict[str, int | None]]:
    """Scrape walk/transit/bike scores from walkscore.com."""
    slug = _build_walkscore_slug(address, city)
    url = f"{WALKSCORE_BASE}/{slug}"

    try:
        resp = await client.get(url)

        if resp.status_code != 200:
            logger.warning(f"Walk Score page returned {resp.status_code} for {url}")
            return None

        soup = BeautifulSoup(resp.content, "html.parser")

        walk = _extract_score(soup, "walk")
        transit = _extract_score(soup, "transit")
        bike = _extract_score(soup, "bike")

        if walk is None and transit is None and bike is None:
            logger.warning(f"No scores found on Walk Score page: {url}")
            return None

        return {"walk_score": walk, "transit_score": transit, "bike_score": bike}

    except Exception as e:
        logger.error(f"Walk Score scrape failed for {url}: {e}")
        return None


async def enrich_with_walk_score(
    address: str,
    city: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Optional[WalkScoreResult]:
    """Geocode (if needed) and scrape Walk Score for an address.

    No API key required — scrapes the public walkscore.com page.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # Geocode if we don't have coordinates
        if latitude is None or longitude is None:
            geo = await geocode_address(address, city, client)
            if geo:
                latitude, longitude = geo
            else:
                # Still try scraping even without coordinates
                latitude = latitude or 0.0
                longitude = longitude or 0.0

        scores = await scrape_walk_score(address, city, client)
        if not scores:
            return None

        return WalkScoreResult(
            walk_score=scores["walk_score"],
            transit_score=scores["transit_score"],
            bike_score=scores["bike_score"],
            latitude=latitude,
            longitude=longitude,
        )
