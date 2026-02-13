#!/usr/bin/env python
"""Manual Walk Score enrichment script.

Processes the backlog of houses without Walk Scores. This provides:
- Geocoded coordinates (latitude/longitude)
- Walk Score (walkability rating 0-100)
- Transit Score (if available)
- Bike Score (if available)
- Postal codes (when available from geocoding)

Run with: python manual_enrich_walkscores.py
"""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path("backend/.env"))

from backend.app.db import (
    close_pool,
    get_listings_without_walk_score,
    init_pool,
    mark_walk_score_failed,
    update_walk_scores,
)
from housemktanalyzr.enrichment.walkscore import enrich_with_walk_score


async def run_enrichment():
    """Run Walk Score enrichment on backlog."""
    await init_pool()

    # Configuration
    batch_size = int(os.getenv("WALK_SCORE_BATCH_SIZE", 100))
    max_batches = int(os.getenv("WALK_SCORE_MAX_BATCHES", 150))
    delay = float(os.getenv("WALK_SCORE_DELAY", 1.2))

    total_enriched = 0
    total_failed = 0
    batch_num = 0

    print("=" * 80)
    print("WALK SCORE ENRICHMENT - PROCESSING BACKLOG")
    print("=" * 80)
    print(f"Batch size: {batch_size}")
    print(f"Max batches: {max_batches} (up to {batch_size * max_batches:,} listings)")
    print(f"Delay: {delay}s per listing")
    print(f"Estimated time: {batch_size * max_batches * delay / 3600:.1f} hours")
    print()

    start_time = datetime.now(timezone.utc)

    try:
        while batch_num < max_batches:
            batch_num += 1

            try:
                listings = await get_listings_without_walk_score(limit=batch_size)
            except Exception as e:
                print(f"\nERROR: ERROR: Failed to query listings: {e}")
                break

            if not listings:
                print(f"\nSUCCESS: Batch {batch_num}: All listings processed!")
                break

            print(f"\n--- Batch {batch_num}/{max_batches} ---")
            print(f"Processing {len(listings)} listings...")
            batch_start = datetime.now(timezone.utc)

            batch_enriched = 0
            batch_failed = 0

            for i, item in enumerate(listings, 1):
                try:
                    result = await enrich_with_walk_score(
                        item["address"],
                        item["city"],
                        latitude=item.get("latitude"),
                        longitude=item.get("longitude"),
                    )

                    if result:
                        await update_walk_scores(
                            item["id"],
                            result.walk_score,
                            result.transit_score,
                            result.bike_score,
                            result.latitude,
                            result.longitude,
                            result.postal_code,
                        )
                        total_enriched += 1
                        batch_enriched += 1
                    else:
                        await mark_walk_score_failed(item["id"])
                        total_failed += 1
                        batch_failed += 1

                    # Progress update every 20 listings
                    if i % 20 == 0:
                        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                        processed = total_enriched + total_failed
                        rate = processed / elapsed if elapsed > 0 else 0
                        remaining = batch_size * max_batches - processed
                        eta_sec = remaining / rate if rate > 0 else 0

                        print(
                            f"  [{i:3}/{len(listings)}] "
                            f"Total: {total_enriched:,} OK / {total_failed:,} FAIL | "
                            f"Rate: {rate:.1f}/s | "
                            f"ETA: {eta_sec/3600:.1f}h"
                        )

                    await asyncio.sleep(delay)

                except asyncio.CancelledError:
                    print("\nWARNING:  Enrichment cancelled by user")
                    raise
                except Exception as e:
                    print(f"  WARNING:  Error enriching {item['id']}: {str(e)[:60]}")
                    try:
                        await mark_walk_score_failed(item["id"])
                    except Exception:
                        pass
                    total_failed += 1
                    batch_failed += 1

            batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
            print(
                f"  Batch complete: {batch_enriched} OK / {batch_failed} FAIL "
                f"in {batch_duration:.0f}s"
            )

    except KeyboardInterrupt:
        print("\n\nWARNING:  Enrichment interrupted by user (Ctrl+C)")
    finally:
        await close_pool()

        total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        total_processed = total_enriched + total_failed

        print("\n" + "=" * 80)
        print("ENRICHMENT SUMMARY")
        print("=" * 80)
        print(f"Total processed:       {total_processed:,}")
        print(f"Successfully enriched: {total_enriched:,} ({total_enriched/total_processed*100:.1f}%)")
        print(f"Failed:                {total_failed:,} ({total_failed/total_processed*100:.1f}%)")
        print(f"Duration:              {total_duration/60:.1f} minutes")
        print(f"Rate:                  {total_processed/total_duration:.1f} listings/second")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_enrichment())
