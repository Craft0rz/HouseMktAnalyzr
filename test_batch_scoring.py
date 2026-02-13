#!/usr/bin/env python
"""Test batched condition scoring."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

from backend.app.db import init_pool, close_pool, get_pool
from housemktanalyzr.enrichment.condition_scorer import score_properties_batch
from datetime import datetime, timezone
import json


async def test_batch_scoring():
    """Test scoring 8 properties in a single API call."""
    await init_pool()
    pool = get_pool()
    now = datetime.now(timezone.utc)

    # Get 8 properties with photos that need scoring
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
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
            LIMIT 8
        """, now)

    if not rows:
        print("No properties found for testing!")
        await close_pool()
        return

    print(f"Testing batch scoring with {len(rows)} properties")
    print("=" * 80)

    # Prepare properties for batch scoring
    properties = []
    property_ids = []
    for row in rows:
        photo_urls = json.loads(row['photo_urls'])
        properties.append({
            "photo_urls": photo_urls,
            "property_type": row['property_type'] or "HOUSE",
            "city": row['city'] or "Montreal",
            "year_built": row['year_built'],
        })
        property_ids.append(row['id'])
        print(f"  Property {len(properties)}: {row['property_type']} in {row['city']}, {len(photo_urls)} photos")

    print("\nCalling Gemini API with batch of 8 properties...")
    print("This counts as 1 API request instead of 8!")

    # Score the batch
    results = await score_properties_batch(properties, max_photos_per_property=5, batch_size=8)

    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)

    for idx, (prop_id, result) in enumerate(zip(property_ids, results)):
        if result:
            print(f"\nProperty {idx + 1} ({prop_id}):")
            print(f"  Overall score: {result.overall_score}/10")
            print(f"  Kitchen: {result.kitchen_score}/10" if result.kitchen_score else "  Kitchen: Not visible")
            print(f"  Bathroom: {result.bathroom_score}/10" if result.bathroom_score else "  Bathroom: Not visible")
            print(f"  Floors: {result.floors_score}/10" if result.floors_score else "  Floors: Not visible")
            print(f"  Exterior: {result.exterior_score}/10" if result.exterior_score else "  Exterior: Not visible")
            print(f"  Renovation needed: {'Yes' if result.renovation_needed else 'No'}")
            print(f"  Notes: {result.notes}")
        else:
            print(f"\nProperty {idx + 1} ({prop_id}): FAILED")

    print("\n" + "=" * 80)
    print("EFFICIENCY GAIN:")
    print("=" * 80)
    successful = sum(1 for r in results if r is not None)
    print(f"Scored {successful} properties with 1 API call")
    print(f"Traditional method would use {successful} API calls")
    print(f"Efficiency gain: {successful}x faster!")
    print(f"\nWith 250 req/day limit:")
    print(f"  Old way: 250 properties/day")
    print(f"  Batch way: {250 * successful} properties/day")
    print(f"  Backlog (13,573) clearable in {13573 / (250 * successful):.1f} days instead of 54!")

    await close_pool()


if __name__ == "__main__":
    asyncio.run(test_batch_scoring())
