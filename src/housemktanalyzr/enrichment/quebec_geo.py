"""Quebec government geo data fetchers for family home scoring.

Fetches school proximity, flood zone, and park data from Quebec open data
sources. All functions accept latitude/longitude coordinates and return
structured data. Failures are handled gracefully (return None/defaults).

Data sources:
- Schools: Quebec MEES ArcGIS endpoint (DonneesOuvertes/SW_MEES layers)
- Flood zones: CEHQ via Donnees Quebec public themes MapServer
- Parks: OpenStreetMap Overpass API (works for all Quebec regions)
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# HTTP timeout for all external API calls (seconds)
_API_TIMEOUT = 5.0

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

                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()

                if data.get("error"):
                    logger.warning(f"School API layer {layer_id} error: {data['error']}")
                    continue

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

        # Sort by distance
        schools.sort(key=lambda s: s["distance_m"] if s["distance_m"] is not None else float("inf"))

        _schools_cache[key] = schools
        return schools

    except httpx.TimeoutException:
        logger.warning(f"School API timeout for ({lat}, {lon})")
        return None
    except Exception as e:
        logger.warning(f"School API error for ({lat}, {lon}): {e}")
        return None


async def check_flood_zone(lat: float, lon: float) -> dict | None:
    """Check if coordinates fall within a Quebec flood zone.

    Uses the CEHQ (Centre d'expertise hydrique du Quebec) ESRI REST API
    to determine if a property is located in a designated flood zone.

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
        "https://servicesgeo.enviroweb.gouv.qc.ca/arcgis/rest/services/"
        "CEHQ/ZonesInondables/MapServer/0/query"
    )
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        features = data.get("features", [])

        if features:
            # Property is in a flood zone
            attrs = features[0].get("attributes", {})
            zone_type = (
                attrs.get("TYPE_ZONE")
                or attrs.get("ZONE_INOND")
                or attrs.get("DESCRIPTION")
                or attrs.get("NOM")
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

    except httpx.TimeoutException:
        logger.warning(f"Flood zone API timeout for ({lat}, {lon})")
        return None
    except Exception as e:
        logger.warning(f"Flood zone API error for ({lat}, {lon}): {e}")
        return None


async def fetch_nearby_parks(
    lat: float, lon: float, radius_m: int = 1000
) -> dict | None:
    """Fetch nearby parks and playgrounds.

    For Montreal area: uses Montreal Open Data API.
    For other areas: falls back to OpenStreetMap Overpass API.

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

    # Determine if coordinates are in Montreal area (rough bounding box)
    is_montreal = (45.40 <= lat <= 45.70) and (-73.97 <= lon <= -73.47)

    result = None
    if is_montreal:
        result = await _fetch_parks_montreal(lat, lon, radius_m)

    # Fall back to OSM Overpass if Montreal API failed or not in Montreal
    if result is None:
        result = await _fetch_parks_osm(lat, lon, radius_m)

    if result is not None:
        _parks_cache[key] = result
    return result


async def _fetch_parks_montreal(
    lat: float, lon: float, radius_m: int
) -> dict | None:
    """Fetch parks from Montreal Open Data CKAN API.

    Montreal publishes park data through their CKAN data portal.
    We search the grands-parcs resource for nearby parks.
    """
    url = "https://donnees.montreal.ca/api/3/action/datastore_search"
    # The exact resource_id may change; we attempt with the known park resource
    # and fall back to OSM if this fails.
    params: dict[str, Any] = {
        "resource_id": "2e9e4d2f-173a-4c3d-a5e3-565d79e1a5c6",
        "limit": 100,
    }

    try:
        async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        records = data.get("result", {}).get("records", [])
        if not records:
            return None

        park_count = 0
        playground_count = 0
        nearest_park_m: float | None = None

        for record in records:
            # Try to extract lat/lon from record
            record_lat = record.get("LATITUDE") or record.get("latitude")
            record_lon = record.get("LONGITUDE") or record.get("longitude")

            if record_lat is None or record_lon is None:
                continue

            try:
                record_lat = float(record_lat)
                record_lon = float(record_lon)
            except (ValueError, TypeError):
                continue

            distance = haversine_distance(lat, lon, record_lat, record_lon)

            if distance <= radius_m:
                park_count += 1
                if nearest_park_m is None or distance < nearest_park_m:
                    nearest_park_m = round(distance)

                # Check if it has playground facilities
                parc_type = str(record.get("TYPE", "") or "").lower()
                if "jeux" in parc_type or "playground" in parc_type:
                    playground_count += 1

        return {
            "park_count": park_count,
            "playground_count": playground_count,
            "nearest_park_m": nearest_park_m,
        }

    except httpx.TimeoutException:
        logger.warning(f"Montreal parks API timeout for ({lat}, {lon})")
        return None
    except Exception as e:
        logger.warning(f"Montreal parks API error for ({lat}, {lon}): {e}")
        return None


async def _fetch_parks_osm(
    lat: float, lon: float, radius_m: int
) -> dict | None:
    """Fetch parks and playgrounds from OpenStreetMap Overpass API.

    Uses the Overpass API to query for leisure=park and leisure=playground
    within the specified radius.
    """
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:5];
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
            resp = await client.post(url, data={"data": query})
            resp.raise_for_status()
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

    except httpx.TimeoutException:
        logger.warning(f"OSM Overpass timeout for ({lat}, {lon})")
        return None
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
