#!/usr/bin/env python
"""Manual batch condition scoring script.

Processes the condition scoring backlog efficiently using batched API calls.
- Scores 8 properties per API call (8x efficiency)
- Respects Gemini free tier: 250 req/day, 10 req/min
- Can process 2,000 properties/day
- Clears 13,573 backlog in ~6.8 days

Usage: python manual_batch_condition_scoring.py
"""

import asyncio
import os
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path("backend/.env"))

from backend.app.db import close_pool, get_pool, init_pool
from housemktanalyzr.enrichment.condition_scorer import score_properties_batch


async def get_properties_needing_scoring(limit: int = 100):
    """Get properties that need condition scoring."""
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                data->>'property_type' as property_type,
                data->>'city' as city,
                (data->>'year_built')::int as year_built,
                data->'photo_urls' as photo_urls
            FROM properties
            WHERE expires_at > $1
              AND status = 'active'
              AND jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
              AND (data->>'condition_score') IS NULL
            ORDER BY (data->>'price')::int DESC NULLS LAST
            LIMIT $2
            """,
            now,
            limit,
        )

    return [
        {
            "id": r["id"],
            "property_type": r["property_type"] or "HOUSE",
            "city": r["city"] or "Montreal",
            "year_built": r["year_built"],
            "photo_urls": json.loads(r["photo_urls"]),
        }
        for r in rows
    ]


async def save_condition_score(property_id: str, result):
    """Save condition score to database."""
    pool = get_pool()

    async with pool.acquire() as conn:
        # Get current data
        row = await conn.fetchrow("SELECT data FROM properties WHERE id = $1", property_id)
        if not row:
            return False

        data = json.loads(row["data"])

        # Add condition score
        data["condition_score"] = result.overall_score
        data["condition_kitchen"] = result.kitchen_score
        data["condition_bathroom"] = result.bathroom_score
        data["condition_floors"] = result.floors_score
        data["condition_exterior"] = result.exterior_score
        data["condition_renovation_needed"] = result.renovation_needed
        data["condition_notes"] = result.notes
        data["condition_scored_at"] = datetime.now(timezone.utc).isoformat()

        # Save back
        await conn.execute(
            "UPDATE properties SET data = $1::jsonb WHERE id = $2",
            json.dumps(data),
            property_id,
        )

    return True


async def run_batch_scoring():
    """Run batched condition scoring on backlog."""
    await init_pool()

    # Configuration
    batch_size = int(os.getenv("CONDITION_BATCH_SIZE", 8))  # Properties per API call
    max_batches = int(os.getenv("CONDITION_MAX_BATCHES", 900))  # API calls per run (flash-lite: 1000 RPD)
    delay = float(os.getenv("CONDITION_DELAY", 4.5))  # Seconds between calls (15/min = 4s + buffer)

    total_scored = 0
    total_failed = 0
    batch_num = 0

    print("=" * 80)
    print("BATCHED CONDITION SCORING - PROCESSING BACKLOG")
    print("=" * 80)
    print(f"Batch size: {batch_size} properties per API call")
    print(f"Max batches: {max_batches} (up to {batch_size * max_batches:,} properties)")
    print(f"Delay: {delay}s between calls ({60/delay:.1f} calls/min)")
    print(f"Estimated time: {max_batches * delay / 3600:.1f} hours")
    print()

    start_time = datetime.now(timezone.utc)

    try:
        while batch_num < max_batches:
            batch_num += 1

            # Get next batch of properties
            try:
                properties = await get_properties_needing_scoring(limit=batch_size)
            except Exception as e:
                print(f"\nERROR: Failed to query properties: {e}")
                break

            if not properties:
                print(f"\nSUCCESS: Batch {batch_num}: All properties processed!")
                break

            print(f"\n--- Batch {batch_num}/{max_batches} ---")
            print(f"Processing {len(properties)} properties in 1 API call...")
            batch_start = datetime.now(timezone.utc)

            # Score the batch
            try:
                results = await score_properties_batch(
                    properties, max_photos_per_property=5, batch_size=batch_size
                )

                # Save results
                batch_scored = 0
                batch_failed = 0

                for prop, result in zip(properties, results):
                    if result:
                        try:
                            await save_condition_score(prop["id"], result)
                            total_scored += 1
                            batch_scored += 1
                        except Exception as e:
                            print(f"  WARNING: Failed to save {prop['id']}: {str(e)[:60]}")
                            total_failed += 1
                            batch_failed += 1
                    else:
                        total_failed += 1
                        batch_failed += 1

                # Progress update
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                processed = total_scored + total_failed
                rate = processed / elapsed if elapsed > 0 else 0
                eta_batches = max_batches - batch_num
                eta_sec = eta_batches * delay

                batch_duration = (datetime.now(timezone.utc) - batch_start).total_seconds()
                print(
                    f"  Batch complete: {batch_scored} OK / {batch_failed} FAIL "
                    f"in {batch_duration:.1f}s"
                )
                print(
                    f"  Total: {total_scored:,} OK / {total_failed:,} FAIL | "
                    f"Rate: {rate:.1f} props/s | "
                    f"ETA: {eta_sec/60:.1f}min"
                )

                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                print("\nWARNING: Scoring cancelled by user")
                raise
            except Exception as e:
                print(f"  WARNING: Batch failed: {str(e)[:100]}")
                total_failed += len(properties)

    except KeyboardInterrupt:
        print("\n\nWARNING: Scoring interrupted by user (Ctrl+C)")
    finally:
        await close_pool()

        total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        total_processed = total_scored + total_failed

        print("\n" + "=" * 80)
        print("SCORING SUMMARY")
        print("=" * 80)
        print(f"Total processed:       {total_processed:,}")
        print(
            f"Successfully scored:   {total_scored:,} ({total_scored/total_processed*100:.1f}%)"
            if total_processed > 0
            else "Successfully scored:   0"
        )
        print(
            f"Failed:                {total_failed:,} ({total_failed/total_processed*100:.1f}%)"
            if total_processed > 0
            else "Failed:                0"
        )
        print(f"Duration:              {total_duration/60:.1f} minutes")
        print(
            f"Rate:                  {total_processed/total_duration:.1f} properties/second"
            if total_duration > 0
            else "Rate:                  N/A"
        )
        print(f"API calls used:        {batch_num}")
        print(f"Efficiency:            {total_processed/batch_num:.1f}x" if batch_num > 0 else "Efficiency:            N/A")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_batch_scoring())
