"""Shared constants for property types, regions, and scrape matrix."""

PROPERTY_TYPE_URLS = {
    "DUPLEX": "/en/duplexes~for-sale~{region}",
    "TRIPLEX": "/en/triplexes~for-sale~{region}",
    "HOUSE": "/en/houses~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",
}

# Primary slug per region (used by all-listings endpoint for direct URL building)
REGION_URL_MAPPING = {
    "montreal": "montreal-island",
    "laval": "laval",
    "south-shore": "montreal-south-shore",
    "rive-sud": "montreal-south-shore",
    "monteregie": "monteregie",
    "north-shore": "montreal-north-shore",
    "laurentides": "laurentides",
    "lanaudiere": "lanaudiere",
}

# Regions that need multiple Centris slugs to cover their full area
_REGION_SCRAPE_SLUGS: dict[str, list[str]] = {
}

# Build scrape matrix: (region_key, type_key, full_url) for all combinations
SCRAPE_MATRIX: list[tuple[str, str, str]] = []
for _region_key, _region_slug in REGION_URL_MAPPING.items():
    if _region_key == "rive-sud":  # alias for south-shore, skip duplicate
        continue
    _slugs = _REGION_SCRAPE_SLUGS.get(_region_key, [_region_slug])
    for _slug in _slugs:
        for _type_key, _url_pattern in PROPERTY_TYPE_URLS.items():
            SCRAPE_MATRIX.append((
                _region_key,
                _type_key,
                f"https://www.centris.ca{_url_pattern.format(region=_slug)}",
            ))
