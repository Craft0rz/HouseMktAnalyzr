#!/usr/bin/env python
"""Manual geo enrichment script.

Processes the geo enrichment backlog for residential properties that have
coordinates but no geo enrichment data (schools, parks, flood zones).

Uses the same APIs as the background worker:
- MEES API for nearby schools
- CEHQ API for flood zones
- OpenStreetMap Overpass API for parks

Usage: python manual_geo_enrichment.py
"""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

from backend.app.db import (
    close_pool,
    get_houses_without_geo_enrichment,
    get_pool,
    init_pool,
    update_geo_enrichment,
)
from housemktanalyzr.enrichment.quebec_geo import (
    check_flood_zone,
    fetch_nearby_parks,
    fetch_nearby_schools,
)


async def enrich_one(item: dict) -> bool:
    """Enrich a single property with geo data. Returns True on success."""
    lat = item["latitude"]
    lon = item["longitude"]

    try:
        schools_data, flood_data, parks_data = await asyncio.gather(
            fetch_nearby_schools(lat, lon),
            check_flood_zone(lat, lon),
            fetch_nearby_parks(lat, lon),
        )

        geo_result = {
            "schools": None,
            "nearest_elementary_m": None,
            "flood_zone": False,
            "flood_zone_type": None,
            "park_count_1km": 0,
            "nearest_park_m": None,
            "safety_score": None,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
        }

        if schools_data:
            geo_result["schools"] = schools_data
            elementary = [
                s for s in schools_data
                if s.get("type") == "elementary" and s.get("distance_m") is not None
            ]
            if elementary:
                geo_result["nearest_elementary_m"] = elementary[0]["distance_m"]
            elif schools_data and schools_data[0].get("distance_m") is not None:
                geo_result["nearest_elementary_m"] = schools_data[0]["distance_m"]

        if flood_data:
            geo_result["flood_zone"] = flood_data.get("in_flood_zone", False)
            geo_result["flood_zone_type"] = flood_data.get("zone_type")

        if parks_data:
            geo_result["park_count_1km"] = parks_data.get("park_count", 0)
            geo_result["nearest_park_m"] = parks_data.get("nearest_park_m")

        await update_geo_enrichment(item["id"], geo_result)
        return True

    except Exception as e:
        print(f"  ERROR enriching {item['id']}: {str(e)[:100]}")
        return False


async def run_geo_enrichment():
    """Run geo enrichment on the backlog."""
    await init_pool()

    batch_size = int(os.getenv("GEO_BATCH_SIZE", "50"))
    max_batches = int(os.getenv("GEO_MAX_BATCHES", "300"))
    concurrency = int(os.getenv("GEO_CONCURRENCY", "5"))
    delay = float(os.getenv("GEO_DELAY", "1.0"))

    total_enriched = 0
    total_failed = 0
    batch_num = 0

    print("=" * 70)
    print("MANUAL GEO ENRICHMENT - PROCESSING BACKLOG")
    print("=" * 70)
    print(f"Batch size: {batch_size} properties per DB query")
    print(f"Max batches: {max_batches} (up to {batch_size * max_batches:,} properties)")
    print(f"Concurrency: {concurrency} parallel API calls")
    print(f"Delay: {delay}s between chunks")
    print()

    start_time = datetime.now(timezone.utc)

    try:
        while batch_num < max_batches:
            batch_num += 1

            try:
                properties = await get_houses_without_geo_enrichment(limit=batch_size)
            except Exception as e:
                print(f"\nERROR: Failed to query properties: {e}")
                break

            if not properties:
                print(f"\nAll properties processed!")
                break

            print(f"\n--- Batch {batch_num}/{max_batches} ({len(properties)} properties) ---")
            batch_start = datetime.now(timezone.utc)
            batch_ok = 0
            batch_fail = 0

            # Process in concurrent chunks
            sem = asyncio.Semaphore(concurrency)

            async def _bounded_enrich(item):
                async with sem:
                    return await enrich_one(item)

            for i in range(0, len(properties), concurrency):
                chunk = properties[i:i + concurrency]
                results = await asyncio.gather(
                    *[_bounded_enrich(p) for p in chunk],
                    return_exceptions=True,
                )
                for r in results:
                    if r is True:
                        batch_ok += 1
                        total_enriched += 1
                    else:
                        batch_fail += 1
                        total_failed += 1
                await asyncio.sleep(delay)

            batch_dur = (datetime.now(timezone.utc) - batch_start).total_seconds()
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            total = total_enriched + total_failed
            rate = total / elapsed if elapsed > 0 else 0

            print(
                f"  Batch: {batch_ok} OK / {batch_fail} FAIL in {batch_dur:.1f}s | "
                f"Total: {total_enriched:,} OK / {total_failed:,} FAIL | "
                f"Rate: {rate:.1f}/s"
            )

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")
    finally:
        await close_pool()

        total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        total_processed = total_enriched + total_failed

        print("\n" + "=" * 70)
        print("GEO ENRICHMENT SUMMARY")
        print("=" * 70)
        print(f"Total processed:     {total_processed:,}")
        if total_processed > 0:
            print(f"Successfully enriched: {total_enriched:,} ({total_enriched/total_processed*100:.1f}%)")
            print(f"Failed:              {total_failed:,} ({total_failed/total_processed*100:.1f}%)")
        print(f"Duration:            {total_duration/60:.1f} minutes")
        if total_duration > 0:
            print(f"Rate:                {total_processed/total_duration:.1f} properties/second")
        print(f"Batches used:        {batch_num}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_geo_enrichment())
