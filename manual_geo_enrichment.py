#!/usr/bin/env python
"""Manual geo enrichment script.

Processes the geo enrichment backlog for residential properties that have
coordinates but no geo enrichment data (schools, parks, flood zones).

Strategy: Schools + flood zones are fast APIs. Parks (OSM Overpass) is slow
and rate-limited. We enrich schools + flood zones first for all properties,
then add parks data in a separate pass with lower concurrency.

Usage:
    python manual_geo_enrichment.py              # Full enrichment (schools+flood+parks)
    python manual_geo_enrichment.py --skip-parks  # Fast pass: schools+flood only
    python manual_geo_enrichment.py --parks-only   # Slow pass: add parks to enriched properties
"""

import asyncio
import json
import os
import sys
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


async def enrich_one(item: dict, skip_parks: bool = False) -> bool:
    """Enrich a single property with geo data. Returns True on success."""
    lat = item["latitude"]
    lon = item["longitude"]

    try:
        # Schools and flood zones are fast - always fetch
        schools_task = fetch_nearby_schools(lat, lon)
        flood_task = check_flood_zone(lat, lon)

        if skip_parks:
            schools_data, flood_data = await asyncio.gather(schools_task, flood_task)
            parks_data = None
        else:
            schools_data, flood_data, parks_data = await asyncio.gather(
                schools_task, flood_task, fetch_nearby_parks(lat, lon)
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

        if skip_parks:
            geo_result["parks_pending"] = True

        await update_geo_enrichment(item["id"], geo_result)
        return True

    except Exception as e:
        print(f"  ERROR enriching {item['id']}: {str(e)[:100]}")
        return False


async def enrich_parks_only(item: dict) -> bool:
    """Add parks data to an already-enriched property."""
    lat = item["latitude"]
    lon = item["longitude"]

    try:
        parks_data = await fetch_nearby_parks(lat, lon)

        # Read existing geo data and update parks fields
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM properties WHERE id = $1", item["id"]
            )
            if not row:
                return False

            data = json.loads(row["data"])
            geo = data.get("raw_data", {}).get("geo_enrichment", {})
            if not geo:
                return False

            if parks_data:
                geo["park_count_1km"] = parks_data.get("park_count", 0)
                geo["nearest_park_m"] = parks_data.get("nearest_park_m")
            geo.pop("parks_pending", None)
            geo["enriched_at"] = datetime.now(timezone.utc).isoformat()

            data["raw_data"]["geo_enrichment"] = geo
            await conn.execute(
                "UPDATE properties SET data = $1::jsonb WHERE id = $2",
                json.dumps(data), item["id"],
            )
        return True

    except Exception as e:
        print(f"  ERROR parks for {item['id']}: {str(e)[:100]}")
        return False


async def get_properties_needing_parks(limit: int = 50) -> list[dict]:
    """Get properties that have geo enrichment but are missing parks data."""
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, data FROM properties
            WHERE expires_at > $1 AND status = 'active'
              AND property_type IN ('HOUSE','DUPLEX','TRIPLEX','QUADPLEX','MULTIPLEX')
              AND data->'raw_data'->'geo_enrichment' IS NOT NULL
              AND COALESCE(data->'raw_data'->'geo_enrichment', 'null'::jsonb) != 'null'::jsonb
              AND (data->'raw_data'->'geo_enrichment'->>'parks_pending')::boolean IS TRUE
            ORDER BY fetched_at DESC
            LIMIT $2
        """, now, limit)

    results = []
    for row in rows:
        data = json.loads(row["data"])
        lat = data.get("latitude")
        lon = data.get("longitude")
        if lat is not None and lon is not None:
            results.append({
                "id": row["id"],
                "latitude": float(lat),
                "longitude": float(lon),
            })
    return results


async def run_geo_enrichment():
    """Run geo enrichment on the backlog."""
    await init_pool()

    skip_parks = "--skip-parks" in sys.argv
    parks_only = "--parks-only" in sys.argv

    batch_size = int(os.getenv("GEO_BATCH_SIZE", "50"))
    max_batches = int(os.getenv("GEO_MAX_BATCHES", "300"))
    delay = float(os.getenv("GEO_DELAY", "0.5"))

    if parks_only:
        concurrency = int(os.getenv("GEO_CONCURRENCY", "2"))
        delay = float(os.getenv("GEO_DELAY", "3.0"))
        mode = "PARKS ONLY (adding to enriched properties)"
    elif skip_parks:
        concurrency = int(os.getenv("GEO_CONCURRENCY", "10"))
        mode = "FAST MODE (schools + flood zones only, skipping parks)"
    else:
        concurrency = int(os.getenv("GEO_CONCURRENCY", "3"))
        delay = float(os.getenv("GEO_DELAY", "2.0"))
        mode = "FULL (schools + flood zones + parks)"

    total_enriched = 0
    total_failed = 0
    batch_num = 0

    print("=" * 70)
    print("MANUAL GEO ENRICHMENT - PROCESSING BACKLOG")
    print("=" * 70)
    print(f"Mode: {mode}")
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
                if parks_only:
                    properties = await get_properties_needing_parks(limit=batch_size)
                else:
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

            async def _bounded(item):
                async with sem:
                    if parks_only:
                        return await enrich_parks_only(item)
                    return await enrich_one(item, skip_parks=skip_parks)

            for i in range(0, len(properties), concurrency):
                chunk = properties[i:i + concurrency]
                results = await asyncio.gather(
                    *[_bounded(p) for p in chunk],
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
