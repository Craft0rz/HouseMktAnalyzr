"""Quebec government geo data fetchers for family home scoring.

Fetches school proximity, flood zone, and park data from Quebec open data
sources. All functions accept latitude/longitude coordinates and return
structured data. Failures are handled gracefully (return None/defaults).

Data sources:
- Schools: Quebec MEES ArcGIS endpoint (DonneesOuvertes/SW_MEES layers)
- Flood zones: CEHQ via Donnees Quebec public themes MapServer
- Parks: OpenStreetMap Overpass API (works for all Quebec regions)
"""

import asyncio
import logging
import math
import os

import httpx

logger = logging.getLogger(__name__)

# HTTP timeout for all external API calls (seconds) — configurable via env var
_API_TIMEOUT = float(os.environ.get("GEO_API_TIMEOUT", 15))

# Retry configuration
_MAX_RETRIES = int(os.environ.get("GEO_API_RETRIES", 2))
_RETRY_DELAY = 2.0  # seconds between retries

# In-memory cache keyed by (round(lat,3), round(lon,3)) to avoid
# repeated calls for nearby properties (within ~111m)
_schools_cache: dict[tuple[float, float], list[dict]] = {}
_flood_cache: dict[tuple[float, float], dict] = {}
_parks_cache: dict[tuple[float, float], dict] = {}


def _cache_key(lat: float, lon: float) -> tuple[float, float]:
    """Round coordinates to 3 decimal places for cache key (~111m precision)."""
    return (round(lat, 3), round(lon, 3))


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in meters between two coordinates using the Haversine formula.

    Args:
        lat1: Latitude of point 1 (degrees).
        lon1: Longitude of point 1 (degrees).
        lat2: Latitude of point 2 (degrees).
        lon2: Longitude of point 2 (degrees).

    Returns:
        Distance in meters.
    """
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _retry_request(
    method: str,
    client: httpx.AsyncClient,
    url: str,
    api_name: str,
    lat: float,
    lon: float,
    **kwargs,
) -> httpx.Response | None:
    """Execute an HTTP request with retry logic and rate limit handling.

    Retries on timeouts, 429 (rate limited), and 5xx server errors.
    Returns None if all retries are exhausted.
    """
    for attempt in range(_MAX_RETRIES + 1):
        try:
            if method == "GET":
                resp = await client.get(url, **kwargs)
            else:
                resp = await client.post(url, **kwargs)

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", _RETRY_DELAY * (attempt + 1)))
                logger.warning(f"{api_name} rate limited (429) for ({lat}, {lon}), retry in {retry_after}s")
                await asyncio.sleep(retry_after)
                continue

            if resp.status_code >= 500:
                logger.warning(f"{api_name} server error {resp.status_code} for ({lat}, {lon}), attempt {attempt + 1}")
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                return None

            resp.raise_for_status()
            return resp

        except httpx.TimeoutException:
            logger.warning(
                f"{api_name} timeout for ({lat}, {lon}), "
                f"attempt {attempt + 1}/{_MAX_RETRIES + 1}"
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
                continue
            return None
        except httpx.HTTPStatusError:
            # 4xx errors (other than 429) are not retryable
            logger.warning(f"{api_name} HTTP error for ({lat}, {lon}): {resp.status_code}")
            return None
        except Exception as e:
            logger.warning(f"{api_name} error for ({lat}, {lon}): {e}")
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY)
                continue
            return None

    return None


async def fetch_nearby_schools(
    lat: float, lon: float, radius_m: int = 2000
) -> list[dict] | None:
    """Fetch nearby schools from Quebec MEES ArcGIS endpoint.

    Uses the Quebec Ministry of Education's GIS service (DonneesOuvertes/SW_MEES)
    to find schools within a given radius. Queries multiple layers to get both
    French and English schools:
      - Layer 3: francophone public
      - Layer 5: anglophone public
      - Layer 9: private schools

    Args:
        lat: Latitude of the property.
        lon: Longitude of the property.
        radius_m: Search radius in meters (default 2000m).

    Returns:
        List of dicts with keys: name, type (elementary/secondary),
        distance_m, language (french/english). Returns None on failure.
    """
    key = _cache_key(lat, lon)
    if key in _schools_cache:
        return _schools_cache[key]

    # Layer ID → language mapping
    layers = {
        3: "french",   # Francophone public
        5: "english",  # Anglophone public
        9: "french",   # Private (default to french, check attrs)
    }

    base_url = (
        "https://infogeo.education.gouv.qc.ca/arcgis/rest/services/"
        "DonneesOuvertes/SW_MEES/MapServer/{layer}/query"
    )

    schools: list[dict] = []
    layers_succeeded = 0

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            for layer_id, default_lang in layers.items():
                url = base_url.format(layer=layer_id)
                params = {
                    "geometry": f"{lon},{lat}",
                    "geometryType": "esriGeometryPoint",
                    "spatialRel": "esriSpatialRelIntersects",
                    "inSR": "4326",
                    "outFields": "*",
                    "distance": str(radius_m),
                    "units": "esriSRUnit_Meter",
                    "returnGeometry": "true",
                    "f": "json",
                }

                resp = await _retry_request(
                    "GET", client, url, f"School API layer {layer_id}",
                    lat, lon, params=params,
                )
                if resp is None:
                    continue

                data = resp.json()

                if data.get("error"):
                    logger.warning(f"School API layer {layer_id} error: {data['error']}")
                    continue

                layers_succeeded += 1

                for feature in data.get("features", []):
                    attrs = feature.get("attributes", {})
                    geom = feature.get("geometry", {})

                    school_lat = geom.get("y")
                    school_lon = geom.get("x")
                    distance_m = None
                    if school_lat is not None and school_lon is not None:
                        distance_m = round(haversine_distance(lat, lon, school_lat, school_lon))

                    school_name = (
                        attrs.get("NOM_OFFCL_ORGNS")
                        or attrs.get("NOM_OFFICI")
                        or attrs.get("NOM_ETABLI")
                        or attrs.get("NOM")
                        or "Unknown"
                    )

                    ordre = (
                        attrs.get("ORDRE_ENS")
                        or attrs.get("ORDRE")
                        or ""
                    ).lower()
                    if "primaire" in ordre or "prescolaire" in ordre:
                        school_type = "elementary"
                    elif "secondaire" in ordre:
                        school_type = "secondary"
                    else:
                        school_type = "other"

                    language = default_lang

                    schools.append({
                        "name": school_name,
                        "type": school_type,
                        "distance_m": distance_m,
                        "language": language,
                    })

        # Only cache if at least one layer succeeded
        if layers_succeeded == 0:
            return None

        # Sort by distance
        schools.sort(key=lambda s: s["distance_m"] if s["distance_m"] is not None else float("inf"))

        _schools_cache[key] = schools
        return schools

    except Exception as e:
        logger.warning(f"School API error for ({lat}, {lon}): {e}")
        return None


async def check_flood_zone(lat: float, lon: float) -> dict | None:
    """Check if coordinates fall within a Quebec flood zone.

    Uses the Donnees Quebec public themes MapServer (layer 22 = flood zone
    polygons) to determine if a property is in a designated flood zone.

    Args:
        lat: Latitude of the property.
        lon: Longitude of the property.

    Returns:
        Dict with keys: in_flood_zone (bool), zone_type (str|None).
        Returns None on failure.
    """
    key = _cache_key(lat, lon)
    if key in _flood_cache:
        return _flood_cache[key]

    url = (
        "https://www.servicesgeo.enviroweb.gouv.qc.ca/donnees/rest/services/"
        "Public/Themes_publics/MapServer/22/query"
    )
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outFields": "*",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            resp = await _retry_request(
                "GET", client, url, "Flood zone API",
                lat, lon, params=params,
            )
            if resp is None:
                return None

            data = resp.json()

        if data.get("error"):
            logger.warning(f"Flood zone API error response: {data['error']}")
            return None

        features = data.get("features", [])

        if features:
            attrs = features[0].get("attributes", {})
            zone_type = (
                attrs.get("Description")
                or attrs.get("TYPE_ZONE")
                or attrs.get("Nm_rapport")
            )
            result = {
                "in_flood_zone": True,
                "zone_type": zone_type,
            }
        else:
            result = {
                "in_flood_zone": False,
                "zone_type": None,
            }

        _flood_cache[key] = result
        return result

    except Exception as e:
        logger.warning(f"Flood zone API error for ({lat}, {lon}): {e}")
        return None


async def fetch_nearby_parks(
    lat: float, lon: float, radius_m: int = 1000
) -> dict | None:
    """Fetch nearby parks and playgrounds using OpenStreetMap Overpass API.

    Works for all Quebec regions (Montreal, Laval, Longueuil, etc.)
    without needing region-specific data sources.

    Args:
        lat: Latitude of the property.
        lon: Longitude of the property.
        radius_m: Search radius in meters (default 1000m).

    Returns:
        Dict with keys: park_count (int), playground_count (int),
        nearest_park_m (float|None). Returns None on failure.
    """
    key = _cache_key(lat, lon)
    if key in _parks_cache:
        return _parks_cache[key]

    result = await _fetch_parks_osm(lat, lon, radius_m)

    if result is not None:
        _parks_cache[key] = result
    return result


async def _fetch_parks_osm(
    lat: float, lon: float, radius_m: int
) -> dict | None:
    """Fetch parks and playgrounds from OpenStreetMap Overpass API.

    Uses the Overpass API to query for leisure=park and leisure=playground
    within the specified radius.
    """
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:12];
    (
      node["leisure"="park"](around:{radius_m},{lat},{lon});
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      node["leisure"="playground"](around:{radius_m},{lat},{lon});
      way["leisure"="playground"](around:{radius_m},{lat},{lon});
    );
    out center;
    """

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            resp = await _retry_request(
                "POST", client, url, "OSM Overpass",
                lat, lon, data={"data": query},
            )
            if resp is None:
                return None

            data = resp.json()

        elements = data.get("elements", [])

        park_count = 0
        playground_count = 0
        nearest_park_m: float | None = None

        for elem in elements:
            # Get coordinates (center for ways, direct for nodes)
            elem_lat = elem.get("lat") or (elem.get("center", {}) or {}).get("lat")
            elem_lon = elem.get("lon") or (elem.get("center", {}) or {}).get("lon")

            if elem_lat is None or elem_lon is None:
                continue

            tags = elem.get("tags", {})
            leisure = tags.get("leisure", "")

            distance = haversine_distance(lat, lon, elem_lat, elem_lon)

            if leisure == "playground":
                playground_count += 1
            elif leisure == "park":
                park_count += 1
                if nearest_park_m is None or distance < nearest_park_m:
                    nearest_park_m = round(distance)

        return {
            "park_count": park_count,
            "playground_count": playground_count,
            "nearest_park_m": nearest_park_m,
        }

    except Exception as e:
        logger.warning(f"OSM Overpass error for ({lat}, {lon}): {e}")
        return None


def clear_caches() -> None:
    """Clear all in-memory geo data caches.

    Useful for testing or when cache should be refreshed.
    """
    _schools_cache.clear()
    _flood_cache.clear()
    _parks_cache.clear()
