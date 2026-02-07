"""Background scraper worker that populates the DB with all Centris listings."""

import asyncio
import logging
import os
from datetime import datetime, timezone

from .constants import SCRAPE_MATRIX
from .db import cache_listings, get_pool, get_listings_without_walk_score, update_walk_scores

logger = logging.getLogger(__name__)


class ScraperWorker:
    """Background worker that periodically scrapes all region/type combinations."""

    def __init__(self, pool, interval_hours: int = 4, ttl_hours: int = 6):
        self._pool = pool
        self._interval_hours = int(os.environ.get("SCRAPER_INTERVAL_HOURS", interval_hours))
        self._ttl_hours = int(os.environ.get("SCRAPER_TTL_HOURS", ttl_hours))
        self._max_pages = int(os.environ.get("SCRAPER_MAX_PAGES", 20))
        self._request_interval = float(os.environ.get("SCRAPER_REQUEST_INTERVAL", 1.2))
        self._task: asyncio.Task | None = None
        self._status: dict = {
            "is_running": False,
            "last_run_started": None,
            "last_run_completed": None,
            "last_run_duration_sec": None,
            "total_listings_stored": 0,
            "errors": [],
            "next_run_at": None,
        }

    async def start(self):
        """Launch the background scrape loop."""
        enabled = os.environ.get("SCRAPER_ENABLED", "true").lower()
        if enabled not in ("true", "1", "yes"):
            logger.info("Background scraper disabled via SCRAPER_ENABLED")
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"Scraper worker started (interval={self._interval_hours}h, "
            f"ttl={self._ttl_hours}h, max_pages={self._max_pages})"
        )

    async def stop(self):
        """Cancel the background task."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Scraper worker stopped")

    def get_status(self) -> dict:
        """Return current worker status."""
        return {**self._status}

    async def _loop(self):
        """Main loop: scrape, sleep, repeat."""
        # Small delay on startup so the API is responsive immediately
        await asyncio.sleep(5)
        while True:
            try:
                await self.run_full_scrape()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scrape cycle failed unexpectedly")

            next_run = datetime.now(timezone.utc).isoformat()
            self._status["next_run_at"] = next_run
            await asyncio.sleep(self._interval_hours * 3600)

    async def run_full_scrape(self):
        """Execute one full scrape cycle across all region/type combos."""
        from housemktanalyzr.collectors.centris import CentrisScraper
        from housemktanalyzr.collectors.base import CaptchaError, RateLimitError

        logger.info("Starting full scrape cycle")
        self._status["is_running"] = True
        start_time = datetime.now(timezone.utc)
        self._status["last_run_started"] = start_time.isoformat()

        total_stored = 0
        errors = []

        try:
            async with CentrisScraper(request_interval=self._request_interval) as scraper:
                for region, prop_type, search_url in SCRAPE_MATRIX:
                    try:
                        listings = await scraper.fetch_all_listings(
                            search_url=search_url,
                            enrich=False,
                            max_pages=self._max_pages,
                        )
                        if listings:
                            count = await cache_listings(
                                listings,
                                ttl_hours=self._ttl_hours,
                                region=region,
                            )
                            total_stored += count
                            logger.info(
                                f"Scraped {region}/{prop_type}: "
                                f"{len(listings)} found, {count} stored"
                            )
                        else:
                            logger.info(f"Scraped {region}/{prop_type}: 0 listings")

                    except (CaptchaError, RateLimitError) as e:
                        msg = f"{region}/{prop_type}: {e}"
                        logger.warning(f"Rate limited — {msg}")
                        errors.append(msg)
                        await asyncio.sleep(30)

                    except asyncio.CancelledError:
                        raise

                    except Exception as e:
                        msg = f"{region}/{prop_type}: {e}"
                        logger.error(f"Error scraping — {msg}")
                        errors.append(msg)

        finally:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            self._status.update({
                "is_running": False,
                "last_run_completed": end_time.isoformat(),
                "last_run_duration_sec": round(duration, 1),
                "total_listings_stored": total_stored,
                "errors": errors,
            })
            logger.info(
                f"Scrape cycle finished: {total_stored} listings stored, "
                f"{len(errors)} errors, {duration:.0f}s elapsed"
            )

        # Run alert checker after scrape completes
        try:
            from .alert_checker import check_all_alerts
            result = await check_all_alerts()
            logger.info(
                f"Alert check complete: {result['alerts_checked']} alerts checked, "
                f"{result['total_new_matches']} new matches, "
                f"{result['notifications_sent']} notifications sent"
            )
        except Exception:
            logger.exception("Alert check failed after scrape cycle")

        # Enrich listings with Walk Scores
        await self._enrich_walk_scores()

    async def _enrich_walk_scores(self):
        """Fetch walk/transit/bike scores for listings that don't have them."""
        from housemktanalyzr.enrichment.walkscore import enrich_with_walk_score

        batch_size = int(os.environ.get("WALKSCORE_BATCH_SIZE", 50))
        delay = float(os.environ.get("WALKSCORE_DELAY", 3.0))

        try:
            listings = await get_listings_without_walk_score(limit=batch_size)
        except Exception:
            logger.exception("Failed to query listings for Walk Score enrichment")
            return

        if not listings:
            logger.info("Walk Score: all listings already enriched")
            return

        logger.info(f"Walk Score: enriching {len(listings)} listings (delay={delay}s)")
        enriched = 0
        failed = 0

        for item in listings:
            try:
                result = await enrich_with_walk_score(
                    address=item["address"],
                    city=item["city"],
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                )
                if result:
                    await update_walk_scores(
                        listing_id=item["id"],
                        walk_score=result.walk_score,
                        transit_score=result.transit_score,
                        bike_score=result.bike_score,
                        latitude=result.latitude,
                        longitude=result.longitude,
                    )
                    enriched += 1
                else:
                    failed += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Walk Score failed for {item['id']}: {e}")
                failed += 1

            await asyncio.sleep(delay)

        logger.info(f"Walk Score enrichment done: {enriched} enriched, {failed} failed")
