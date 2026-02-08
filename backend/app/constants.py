"""Shared constants for property types, regions, CMAs, and scrape matrix."""

# Scrape URLs — only non-overlapping categories.
# ALL_PLEX covers duplex through quintuplex+; individual types classified after parsing.
SCRAPE_TYPE_URLS = {
    "HOUSE": "/en/houses~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",
}

# Full type-to-URL mapping for on-demand API searches.
# DUPLEX/TRIPLEX have dedicated Centris URLs; QUADPLEX/MULTIPLEX fall back to ALL_PLEX.
PROPERTY_TYPE_URLS = {
    "HOUSE": "/en/houses~for-sale~{region}",
    "DUPLEX": "/en/duplexes~for-sale~{region}",
    "TRIPLEX": "/en/triplexes~for-sale~{region}",
    "QUADPLEX": "/en/plexes~for-sale~{region}",
    "MULTIPLEX": "/en/plexes~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",
}

# Primary slug per region — uses Centris Geographic Areas (Level 1 only).
# Avoids Level 2 sub-areas (e.g. montreal-north-shore) to prevent overlap.
# See sitemap: propertysubtype-sellingtype-geographicarea-1.xml
REGION_URL_MAPPING = {
    "montreal": "montreal-island",
    "laval": "laval",
    "south-shore": "monteregie",
    "rive-sud": "monteregie",       # alias for south-shore
    "laurentides": "laurentides",
    "lanaudiere": "lanaudiere",
    "capitale-nationale": "capitale-nationale",
    "estrie": "estrie",
}

# Build scrape matrix: (region_key, type_key, full_url) for all combinations
SCRAPE_MATRIX: list[tuple[str, str, str]] = []
for _region_key, _region_slug in REGION_URL_MAPPING.items():
    if _region_key == "rive-sud":  # alias for south-shore, skip duplicate
        continue
    for _type_key, _url_pattern in SCRAPE_TYPE_URLS.items():
        SCRAPE_MATRIX.append((
            _region_key,
            _type_key,
            f"https://www.centris.ca{_url_pattern.format(region=_region_slug)}",
        ))

# ---------------------------------------------------------------------------
# CMA (Census Metropolitan Area) configuration
# ---------------------------------------------------------------------------

# Each CMA we actively support for CMHC rent data + demographics.
# cmhc_geo_id: CMHC HMIP internal GeographyId (used by CMHCClient)
# fallback_zone: zone label stored in rent_data for CMA-total rows
CMA_CONFIG: dict[str, dict] = {
    "montreal": {
        "cmhc_geo_id": "1060",
        "fallback_zone": "Montreal CMA Total",
    },
    "quebec": {
        "cmhc_geo_id": "1400",
        "fallback_zone": "Quebec CMA Total",
    },
    "sherbrooke": {
        "cmhc_geo_id": "1800",
        "fallback_zone": "Sherbrooke CMA Total",
    },
}

# Region → CMA mapping. Every region in REGION_URL_MAPPING should map here.
REGION_CMA: dict[str, str] = {
    "montreal": "montreal",
    "laval": "montreal",
    "south-shore": "montreal",
    "rive-sud": "montreal",
    "laurentides": "montreal",
    "lanaudiere": "montreal",
    "capitale-nationale": "quebec",
    "estrie": "sherbrooke",
}


def get_active_cmas() -> list[str]:
    """Return unique CMA keys referenced by active regions."""
    return sorted(set(
        cma for region, cma in REGION_CMA.items()
        if region != "rive-sud"  # skip alias
    ))
