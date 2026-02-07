"""Alert matching engine that checks alerts against DB listings."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from housemktanalyzr.analysis.ranker import PropertyRanker
from housemktanalyzr.models.property import PropertyListing

from .db import get_pool

logger = logging.getLogger(__name__)

ranker = PropertyRanker()


async def check_all_alerts() -> dict:
    """Check all enabled alerts against current listings.

    Returns summary of matches found and notifications sent.
    """
    pool = get_pool()
    now = datetime.now(timezone.utc)

    async with pool.acquire() as conn:
        alerts = await conn.fetch(
            "SELECT * FROM alerts WHERE enabled = TRUE"
        )

    if not alerts:
        return {"alerts_checked": 0, "total_new_matches": 0, "total_price_drops": 0}

    total_new_matches = 0
    total_price_drops = 0
    notifications_sent = 0

    for alert in alerts:
        try:
            result = await _check_single_alert(alert, now)
            total_new_matches += result["new_matches"]
            total_price_drops += result["price_drops"]
            if result["notified"]:
                notifications_sent += 1
        except Exception as e:
            logger.error(f"Error checking alert '{alert['name']}': {e}")

    return {
        "alerts_checked": len(alerts),
        "total_new_matches": total_new_matches,
        "total_price_drops": total_price_drops,
        "notifications_sent": notifications_sent,
    }


async def _check_single_alert(alert, now: datetime) -> dict:
    """Check one alert against DB listings and update matches."""
    pool = get_pool()
    alert_id = alert["id"]

    # Step 1: Query DB for listings matching basic criteria
    listings = await _query_matching_listings(alert, now)

    if not listings:
        await _update_alert_status(alert_id, now, 0)
        return {"new_matches": 0, "price_drops": 0, "notified": False}

    # Step 2: Run investment analysis
    results = ranker.analyze_batch(listings)

    # Step 3: Filter by investment criteria
    filtered = _apply_investment_filters(results, alert)

    # Step 4: Compare with existing matches to find new ones
    matched_ids = {listing.id for listing, _ in filtered}
    new_match_ids = await _find_new_matches(alert_id, matched_ids)

    # Step 5: Check for price drops on matched listings
    price_drops = await _find_price_drops(matched_ids, now)

    # Step 6: Record new matches
    if new_match_ids:
        async with pool.acquire() as conn:
            for prop_id in new_match_ids:
                await conn.execute(
                    """
                    INSERT INTO alert_matches (alert_id, property_id, first_matched_at, notified)
                    VALUES ($1, $2, $3, FALSE)
                    ON CONFLICT (alert_id, property_id) DO NOTHING
                    """,
                    alert_id, prop_id, now,
                )

    # Step 7: Clean up matches that no longer match
    async with pool.acquire() as conn:
        if matched_ids:
            placeholders = ", ".join(f"${i+2}" for i in range(len(matched_ids)))
            await conn.execute(
                f"DELETE FROM alert_matches WHERE alert_id = $1 AND property_id NOT IN ({placeholders})",
                alert_id, *matched_ids,
            )
        else:
            await conn.execute(
                "DELETE FROM alert_matches WHERE alert_id = $1", alert_id
            )

    # Step 8: Send notification if applicable
    notified = False
    notify_email = alert["notify_email"]
    has_new = len(new_match_ids) > 0 and alert["notify_on_new"]
    has_drops = len(price_drops) > 0 and alert["notify_on_price_drop"]

    if notify_email and (has_new or has_drops):
        try:
            from .email_sender import send_alert_email
            new_listings = [
                (l, m) for l, m in filtered if l.id in new_match_ids
            ] if has_new else []
            await send_alert_email(
                to_email=notify_email,
                alert_name=alert["name"],
                new_listings=new_listings,
                price_drops=price_drops,
            )
            notified = True
            # Mark matches as notified
            if new_match_ids:
                async with pool.acquire() as conn:
                    placeholders = ", ".join(f"${i+2}" for i in range(len(new_match_ids)))
                    await conn.execute(
                        f"UPDATE alert_matches SET notified = TRUE WHERE alert_id = $1 AND property_id IN ({placeholders})",
                        alert_id, *new_match_ids,
                    )
        except Exception as e:
            logger.warning(f"Failed to send email for alert '{alert['name']}': {e}")

    # Step 9: Update alert status
    await _update_alert_status(alert_id, now, len(matched_ids))

    if new_match_ids or price_drops:
        logger.info(
            f"Alert '{alert['name']}': {len(matched_ids)} matches, "
            f"{len(new_match_ids)} new, {len(price_drops)} price drops"
        )

    return {
        "new_matches": len(new_match_ids),
        "price_drops": len(price_drops),
        "notified": notified,
    }


async def _query_matching_listings(alert, now: datetime) -> list[PropertyListing]:
    """Query DB for listings matching alert's basic criteria (region, type, price)."""
    pool = get_pool()
    conditions = ["expires_at > $1"]
    params: list = [now]
    idx = 2

    # Region filter
    regions = alert["regions"]
    if isinstance(regions, str):
        regions = json.loads(regions)
    if regions:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(regions)))
        conditions.append(f"region IN ({placeholders})")
        params.extend(regions)
        idx += len(regions)

    # Property type filter
    types = alert["property_types"]
    if isinstance(types, str):
        types = json.loads(types)
    if types:
        placeholders = ", ".join(f"${idx + i}" for i in range(len(types)))
        conditions.append(f"property_type IN ({placeholders})")
        params.extend(types)
        idx += len(types)

    # Price filters
    if alert["min_price"] is not None:
        conditions.append(f"price >= ${idx}")
        params.append(alert["min_price"])
        idx += 1
    if alert["max_price"] is not None:
        conditions.append(f"price <= ${idx}")
        params.append(alert["max_price"])
        idx += 1

    where = " AND ".join(conditions)
    query = f"SELECT data FROM properties WHERE {where} ORDER BY price LIMIT 2000"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [PropertyListing(**json.loads(row["data"])) for row in rows]


def _apply_investment_filters(
    results: list[tuple[PropertyListing, object]],
    alert,
) -> list[tuple[PropertyListing, object]]:
    """Filter analyzed results by investment criteria."""
    filtered = []
    for listing, metrics in results:
        if alert["min_score"] is not None and metrics.score < alert["min_score"]:
            continue
        if alert["min_cap_rate"] is not None and (
            metrics.cap_rate is None or metrics.cap_rate < alert["min_cap_rate"]
        ):
            continue
        if alert["min_cash_flow"] is not None and (
            metrics.cash_flow_monthly is None
            or metrics.cash_flow_monthly < alert["min_cash_flow"]
        ):
            continue
        if alert["max_price_per_unit"] is not None and (
            metrics.price_per_unit > alert["max_price_per_unit"]
        ):
            continue
        if alert["min_yield"] is not None and (
            metrics.gross_rental_yield < alert["min_yield"]
        ):
            continue
        filtered.append((listing, metrics))
    return filtered


async def _find_new_matches(alert_id: str, matched_ids: set[str]) -> set[str]:
    """Find which matched IDs are new (not in alert_matches table)."""
    if not matched_ids:
        return set()

    pool = get_pool()
    async with pool.acquire() as conn:
        placeholders = ", ".join(f"${i+2}" for i in range(len(matched_ids)))
        existing = await conn.fetch(
            f"SELECT property_id FROM alert_matches WHERE alert_id = $1 AND property_id IN ({placeholders})",
            alert_id, *matched_ids,
        )
    existing_ids = {r["property_id"] for r in existing}
    return matched_ids - existing_ids


async def _find_price_drops(
    property_ids: set[str], now: datetime
) -> list[dict]:
    """Find recent price drops for the given properties."""
    if not property_ids:
        return []

    pool = get_pool()
    since = now - timedelta(hours=8)  # Look for drops since last scrape cycle

    async with pool.acquire() as conn:
        placeholders = ", ".join(f"${i+2}" for i in range(len(property_ids)))
        rows = await conn.fetch(
            f"""
            SELECT ph.property_id, ph.old_price, ph.new_price, ph.recorded_at,
                   p.data
            FROM price_history ph
            JOIN properties p ON p.id = ph.property_id
            WHERE ph.property_id IN ({placeholders})
              AND ph.recorded_at > $1
              AND ph.new_price < ph.old_price
            ORDER BY ph.recorded_at DESC
            """,
            since, *property_ids,
        )

    return [
        {
            "property_id": r["property_id"],
            "old_price": r["old_price"],
            "new_price": r["new_price"],
            "drop_amount": r["old_price"] - r["new_price"],
            "drop_pct": round(
                (r["old_price"] - r["new_price"]) / r["old_price"] * 100, 1
            ),
            "address": json.loads(r["data"]).get("address", "Unknown"),
            "recorded_at": r["recorded_at"].isoformat(),
        }
        for r in rows
    ]


async def _update_alert_status(alert_id: str, now: datetime, match_count: int):
    """Update alert's last_checked and last_match_count."""
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE alerts SET last_checked = $1, last_match_count = $2 WHERE id = $3",
            now, match_count, alert_id,
        )
