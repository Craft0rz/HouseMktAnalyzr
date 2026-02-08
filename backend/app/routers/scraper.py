"""Scraper worker status and control endpoints."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from ..db import get_scraper_stats, get_scrape_job_history, get_data_freshness

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def scraper_status(request: Request) -> dict:
    """Return the background scraper worker's current status."""
    worker = request.app.state.scraper_worker
    if worker is None:
        return {"enabled": False, "message": "Scraper not available (no database)"}
    return worker.get_status()


@router.post("/trigger", status_code=202)
async def trigger_scrape(request: Request) -> dict:
    """Manually trigger a full scrape cycle."""
    worker = request.app.state.scraper_worker
    if worker is None:
        raise HTTPException(503, "Scraper not available (no database)")
    if worker.get_status()["is_running"]:
        raise HTTPException(409, "Scrape already in progress")

    asyncio.create_task(worker.run_full_scrape())
    return {"status": "triggered", "message": "Full scrape started"}


@router.get("/stats")
async def scraper_stats() -> dict:
    """Return per-region/type listing counts from the database."""
    try:
        return await get_scraper_stats()
    except Exception as e:
        raise HTTPException(500, f"Failed to get stats: {e}")


@router.get("/history")
async def scraper_history(limit: int = 20) -> dict:
    """Return recent scrape job history from the database."""
    try:
        jobs = await get_scrape_job_history(limit=limit)
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(500, f"Failed to get history: {e}")


@router.get("/freshness")
async def data_freshness() -> dict:
    """Return data freshness indicators for all data sources."""
    try:
        return await get_data_freshness()
    except Exception as e:
        raise HTTPException(500, f"Failed to get freshness data: {e}")
