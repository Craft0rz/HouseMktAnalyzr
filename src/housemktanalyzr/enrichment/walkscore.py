"""Walk Score API integration with Nominatim geocoding."""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WALKSCORE_URL = "https://api.walkscore.com/score"


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


async def fetch_walk_score(
    address: str,
    latitude: float,
    longitude: float,
    api_key: str,
    client: httpx.AsyncClient,
) -> Optional[WalkScoreResult]:
    """Fetch Walk Score, Transit Score, and Bike Score from the Walk Score API."""
    params = {
        "format": "json",
        "address": address,
        "lat": str(latitude),
        "lon": str(longitude),
        "transit": "1",
        "bike": "1",
        "wsapikey": api_key,
    }

    try:
        resp = await client.get(WALKSCORE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != 1:
            logger.warning(f"Walk Score API status {data.get('status')} for {address}")
            return None

        return WalkScoreResult(
            walk_score=data.get("walkscore"),
            transit_score=data.get("transit", {}).get("score"),
            bike_score=data.get("bike", {}).get("score"),
            latitude=latitude,
            longitude=longitude,
        )
    except Exception as e:
        logger.error(f"Walk Score API call failed: {e}")
        return None


async def enrich_with_walk_score(
    address: str,
    city: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> Optional[WalkScoreResult]:
    """Geocode (if needed) and fetch Walk Score for an address.

    Reads WALKSCORE_API_KEY from environment. Returns None if no key
    is configured or if any step fails.
    """
    api_key = os.environ.get("WALKSCORE_API_KEY")
    if not api_key:
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        if latitude is None or longitude is None:
            geo = await geocode_address(address, city, client)
            if not geo:
                return None
            latitude, longitude = geo

        full_address = f"{address}, {city}, QC, Canada"
        return await fetch_walk_score(full_address, latitude, longitude, api_key, client)
