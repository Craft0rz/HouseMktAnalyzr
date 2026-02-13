"""Scraper worker status and control endpoints (admin only)."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import get_admin_user
from ..db import get_scraper_stats, get_scrape_job_history, get_data_freshness, get_geo_enrichment_stats, get_enrichment_backlog, get_pool

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def scraper_status(request: Request, _admin: dict = Depends(get_admin_user)) -> dict:
    """Return the background scraper worker's current status with actionable alerts."""
    worker = request.app.state.scraper_worker
    if worker is None:
        return {"enabled": False, "message": "Scraper not available (no database)"}

    status = worker.get_status()
    alerts = {
        "critical": [],
        "warnings": [],
    }

    # Add data quality stats
    try:
        from ..db import get_data_quality_summary
        status["data_quality"] = await get_data_quality_summary()
    except Exception:
        status["data_quality"] = {}

    # Add geo enrichment stats with severity
    try:
        geo_stats = await get_geo_enrichment_stats()
        status["geo_stats"] = geo_stats
        if geo_stats.get("status") == "critical" and geo_stats.get("action"):
            alerts["critical"].append(geo_stats["action"])
        elif geo_stats.get("status") == "warning" and geo_stats.get("action"):
            alerts["warnings"].append(geo_stats["action"])
    except Exception:
        status["geo_stats"] = {}

    # Add enrichment backlog with severity
    try:
        backlog = await get_enrichment_backlog()
        status["enrichment_backlog"] = backlog
        for item in backlog.get("datapoints", []):
            if item.get("status") == "critical" and item.get("action"):
                alerts["critical"].append(item["action"])
            elif item.get("status") == "warning" and item.get("action"):
                alerts["warnings"].append(item["action"])
    except Exception:
        status["enrichment_backlog"] = {}

    # Add data freshness with severity
    try:
        freshness = await get_data_freshness()
        status["data_freshness"] = freshness
        for key, data in freshness.items():
            if data.get("status") == "critical" and data.get("action"):
                alerts["critical"].append(data["action"])
            elif data.get("status") == "warning" and data.get("action"):
                alerts["warnings"].append(data["action"])
    except Exception:
        status["data_freshness"] = {}

    # Add consolidated alerts at top level for easy frontend access
    status["alerts"] = alerts
    status["has_critical_issues"] = len(alerts["critical"]) > 0
    status["total_issues"] = len(alerts["critical"]) + len(alerts["warnings"])

    return status


@router.post("/trigger", status_code=202)
async def trigger_scrape(request: Request, _admin: dict = Depends(get_admin_user)) -> dict:
    """Manually trigger a full scrape cycle."""
    worker = request.app.state.scraper_worker
    if worker is None:
        raise HTTPException(503, "Scraper not available (no database)")
    if worker.get_status()["is_running"]:
        raise HTTPException(409, "Scrape already in progress")

    asyncio.create_task(worker.run_full_scrape())
    return {"status": "triggered", "message": "Full scrape started"}


@router.get("/stats")
async def scraper_stats(_admin: dict = Depends(get_admin_user)) -> dict:
    """Return per-region/type listing counts from the database."""
    try:
        return await get_scraper_stats()
    except Exception as e:
        raise HTTPException(500, f"Failed to get stats: {e}")


@router.get("/history")
async def scraper_history(limit: int = 20, _admin: dict = Depends(get_admin_user)) -> dict:
    """Return recent scrape job history from the database."""
    try:
        jobs = await get_scrape_job_history(limit=limit)
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(500, f"Failed to get history: {e}")


@router.get("/freshness")
async def data_freshness(_admin: dict = Depends(get_admin_user)) -> dict:
    """Return data freshness indicators for all data sources."""
    try:
        return await get_data_freshness()
    except Exception as e:
        raise HTTPException(500, f"Failed to get freshness data: {e}")


@router.post("/revalidate", status_code=202)
async def revalidate_listings(request: Request, _admin: dict = Depends(get_admin_user)) -> dict:
    """Clear detail_enriched_at markers to force re-validation of all listings.

    The next enrichment cycle will re-fetch detail pages and auto-correct
    any discrepancies between search card data and detail page data.
    """
    worker = request.app.state.scraper_worker
    if worker is None:
        raise HTTPException(503, "Scraper not available (no database)")

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE properties
            SET data = data - 'detail_enriched_at'
            WHERE (data->>'detail_enriched_at') IS NOT NULL
            """
        )
        # Result is like "UPDATE 123"
        count = int(result.split()[-1]) if result else 0

    return {
        "status": "markers_cleared",
        "listings_to_revalidate": count,
        "message": f"Cleared {count} listings. They will be re-validated on next enrichment cycle.",
    }


@router.post("/reset-photos", status_code=202)
async def reset_photos(request: Request, _admin: dict = Depends(get_admin_user)) -> dict:
    """Clear photo_fetch_attempted_at and photo_urls to force re-fetching.

    The next enrichment cycle will attempt to fetch photos for all cleared listings.
    """
    worker = request.app.state.scraper_worker
    if worker is None:
        raise HTTPException(503, "Scraper not available (no database)")

    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE properties
            SET data = data - 'photo_fetch_attempted_at' - 'photo_urls'
            WHERE (data->>'photo_fetch_attempted_at') IS NOT NULL
            """
        )
        # Result is like "UPDATE 123"
        count = int(result.split()[-1]) if result else 0

    return {
        "status": "photo_markers_cleared",
        "listings_to_refetch": count,
        "message": f"Cleared photos for {count} listings. They will be re-fetched on next enrichment cycle.",
    }
