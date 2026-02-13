#!/usr/bin/env python
"""Analyze condition scoring backlog and costs."""

import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path("backend/.env"))

from backend.app.db import init_pool, close_pool, get_pool
from datetime import datetime, timezone


async def main():
    await init_pool()
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        # Overall stats
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
                ) as has_photos,
                COUNT(*) FILTER (
                    WHERE (data->>'condition_score') IS NOT NULL
                ) as has_condition,
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
                      AND (data->>'condition_score') IS NULL
                ) as needs_scoring
            FROM properties
            WHERE expires_at > $1 AND status = 'active'
        """, now)

        total = stats['total']
        has_photos = stats['has_photos']
        has_condition = stats['has_condition']
        needs_scoring = stats['needs_scoring']

        print('CONDITION SCORING ANALYSIS')
        print('=' * 80)
        print(f'Total active listings: {total:,}')
        print(f'With photos: {has_photos:,} ({has_photos/total*100:.1f}%)')
        print(f'Already scored: {has_condition:,} ({has_condition/total*100:.1f}%)')
        print(f'NEED SCORING (have photos): {needs_scoring:,}')
        print()

        # Gemini free tier limits
        daily_limit = 250
        rpm_limit = 10

        days_needed = needs_scoring / daily_limit
        hours_at_rpm = needs_scoring / (rpm_limit * 60)

        print('GEMINI FREE TIER COST ANALYSIS:')
        print('=' * 80)
        print(f'Free tier: {daily_limit} req/day, {rpm_limit} req/min')
        print(f'Time to complete at daily limit: {days_needed:.1f} days ({days_needed/30:.1f} months)')
        print(f'Time if maxing out RPM limit: {hours_at_rpm:.1f} hours ({hours_at_rpm/24:.1f} days)')
        print()

        # Strategy options
        print('COST-EFFECTIVE STRATEGIES:')
        print('=' * 80)
        print(f'1. HOUSES ONLY STRATEGY:')
        house_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
                      AND (data->>'condition_score') IS NULL
                ) as needs_scoring
            FROM properties
            WHERE expires_at > $1 AND status = 'active' AND property_type = 'HOUSE'
        """, now)
        houses_need = house_stats['needs_scoring']
        print(f'   Houses needing scoring: {houses_need:,}')
        print(f'   Time at 250/day: {houses_need/250:.1f} days ({houses_need/250/30:.1f} months)')
        print()

        print(f'2. HIGH-VALUE ONLY (>$500k):')
        highvalue_stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (
                    WHERE jsonb_array_length(COALESCE(data->'photo_urls', '[]'::jsonb)) > 0
                      AND (data->>'condition_score') IS NULL
                ) as needs_scoring
            FROM properties
            WHERE expires_at > $1 AND status = 'active'
              AND (data->>'price')::int > 500000
        """, now)
        highvalue_need = highvalue_stats['needs_scoring']
        print(f'   High-value listings needing scoring: {highvalue_need:,}')
        print(f'   Time at 250/day: {highvalue_need/250:.1f} days')
        print()

        print(f'3. PRIORITIZE BY RECENCY:')
        print(f'   Process newest 2,500 first (10 days at 250/day)')
        print(f'   Let backlog accumulate, process weekly batch')
        print()

        print('RECOMMENDATION:')
        print('=' * 80)
        print('Start with HIGH-VALUE HOUSES (>$500k) ONLY')
        print('This focuses on properties where condition matters most to buyers')
        print('Can expand to all houses later if needed')

    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
