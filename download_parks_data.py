#!/usr/bin/env python
"""Download all parks and playgrounds in southern Quebec from OpenStreetMap.

Makes a SINGLE bulk Overpass API query covering the populated parts of Quebec
(Montreal to Quebec City), saving results to data/quebec_parks.json.

This replaces the per-property Overpass API approach which was rate-limited
to ~2 requests/minute. With local data, park lookups are instant.

Usage: python download_parks_data.py
"""

import json
import time
from pathlib import Path

import httpx

# Southern Quebec bounding box (covers Montreal, Laval, Longueuil, Gatineau,
# Sherbrooke, Trois-Rivieres, Quebec City, Saguenay, and surroundings)
BBOX = {
    "south": 44.9,
    "west": -79.5,
    "north": 49.0,
    "east": -64.0,
}

OUTPUT_FILE = Path(__file__).parent / "data" / "quebec_parks.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Overpass query: get all parks and playgrounds in the bounding box
QUERY = f"""
[out:json][timeout:120];
(
  node["leisure"="park"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
  way["leisure"="park"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
  relation["leisure"="park"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
  node["leisure"="playground"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
  way["leisure"="playground"]({BBOX['south']},{BBOX['west']},{BBOX['north']},{BBOX['east']});
);
out center;
"""


def download():
    """Download parks data from Overpass API."""
    print("Downloading all parks and playgrounds in southern Quebec...")
    print(f"Bounding box: {BBOX}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    start = time.time()

    with httpx.Client(timeout=180) as client:
        resp = client.post(OVERPASS_URL, data={"data": QUERY})
        resp.raise_for_status()
        data = resp.json()

    elements = data.get("elements", [])
    elapsed = time.time() - start
    print(f"Downloaded {len(elements):,} elements in {elapsed:.1f}s")

    # Extract compact park records: (lat, lon, type, name)
    parks = []
    skipped = 0

    for elem in elements:
        # Get coordinates
        lat = elem.get("lat")
        lon = elem.get("lon")

        # For ways/relations, use the center point
        if lat is None or lon is None:
            center = elem.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")

        if lat is None or lon is None:
            skipped += 1
            continue

        tags = elem.get("tags", {})
        leisure = tags.get("leisure", "")
        name = tags.get("name", "")

        parks.append({
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "type": leisure,  # "park" or "playground"
            "name": name,
        })

    # Save to JSON
    output = {
        "bbox": BBOX,
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_elements": len(elements),
        "total_parks": sum(1 for p in parks if p["type"] == "park"),
        "total_playgrounds": sum(1 for p in parks if p["type"] == "playground"),
        "parks": parks,
    }

    OUTPUT_FILE.write_text(json.dumps(output, separators=(",", ":")))
    file_size = OUTPUT_FILE.stat().st_size

    print(f"\nSaved {len(parks):,} parks/playgrounds to {OUTPUT_FILE}")
    print(f"  Parks: {output['total_parks']:,}")
    print(f"  Playgrounds: {output['total_playgrounds']:,}")
    print(f"  Skipped (no coords): {skipped}")
    print(f"  File size: {file_size / 1024:.1f} KB")


if __name__ == "__main__":
    download()
