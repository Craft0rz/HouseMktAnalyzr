"""Shared constants for property types, regions, and scrape matrix."""

PROPERTY_TYPE_URLS = {
    "DUPLEX": "/en/duplexes~for-sale~{region}",
    "TRIPLEX": "/en/triplexes~for-sale~{region}",
    "HOUSE": "/en/houses~for-sale~{region}",
    "ALL_PLEX": "/en/plexes~for-sale~{region}",
}

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

# Build scrape matrix: (region_key, type_key, full_url) for all combinations
SCRAPE_MATRIX: list[tuple[str, str, str]] = []
for _region_key, _region_slug in REGION_URL_MAPPING.items():
    if _region_key == "rive-sud":  # alias for south-shore, skip duplicate
        continue
    for _type_key, _url_pattern in PROPERTY_TYPE_URLS.items():
        SCRAPE_MATRIX.append((
            _region_key,
            _type_key,
            f"https://www.centris.ca{_url_pattern.format(region=_region_slug)}",
        ))
