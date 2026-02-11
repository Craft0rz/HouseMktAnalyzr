"""Background scraper worker that populates the DB with all Centris listings."""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from .constants import SCRAPE_MATRIX
from datetime import timedelta

from .db import (
    cache_listings, get_pool,
    get_listings_without_details, update_listing_details,
    get_listings_without_walk_score, update_walk_scores,
    get_listings_without_photos, update_photo_urls,
    get_listings_without_condition_score, update_condition_score,
    upsert_market_data, get_market_data_age,
    upsert_rent_data_batch, get_rent_data_age,
    upsert_demographics_batch, get_demographics_age,
    upsert_neighbourhood_stats_batch, get_neighbourhood_stats_age,
    upsert_tax_rate_history_batch,
    mark_stale_listings, mark_delisted,
    insert_scrape_job, get_data_quality_summary,
)

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
            "data_warnings": [],
            "next_run_at": None,
            "current_phase": None,
            "current_step": 0,
            "total_steps": len(SCRAPE_MATRIX),
            "current_region": None,
            "current_type": None,
            "step_results": [],
            "enrichment_progress": {
                "details": {"total": 0, "done": 0, "failed": 0, "corrections": 0, "phase": "pending"},
                "walk_scores": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
                "photos": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
                "conditions": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
                "validation": {"total": 0, "corrected": 0, "flagged": 0, "phase": "pending"},
            },
            "refresh_progress": {
                "market": {"status": "pending"},
                "rent": {"status": "pending"},
                "demographics": {"status": "pending"},
                "neighbourhood": {"status": "pending"},
            },
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

            next_run = (datetime.now(timezone.utc) + timedelta(hours=self._interval_hours)).isoformat()
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

        # Reset progress tracking
        self._status["current_phase"] = "scraping"
        self._status["current_step"] = 0
        self._status["step_results"] = []
        self._status["enrichment_progress"] = {
            "details": {"total": 0, "done": 0, "failed": 0, "corrections": 0, "phase": "pending"},
            "walk_scores": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
            "photos": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
            "conditions": {"total": 0, "done": 0, "failed": 0, "phase": "pending"},
            "validation": {"total": 0, "corrected": 0, "flagged": 0, "phase": "pending"},
        }
        self._status["refresh_progress"] = {
            "market": {"status": "pending"},
            "rent": {"status": "pending"},
            "demographics": {"status": "pending"},
            "neighbourhood": {"status": "pending"},
        }

        total_stored = 0
        errors = []

        try:
            async with CentrisScraper(request_interval=self._request_interval) as scraper:
                for step_idx, (region, prop_type, search_url) in enumerate(SCRAPE_MATRIX, 1):
                    self._status["current_step"] = step_idx
                    self._status["current_region"] = region
                    self._status["current_type"] = prop_type
                    step_start = datetime.now(timezone.utc)
                    step_count = 0
                    step_error = None

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
                            step_count = count
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
                        step_error = str(e)
                        await asyncio.sleep(30)

                    except asyncio.CancelledError:
                        raise

                    except Exception as e:
                        msg = f"{region}/{prop_type}: {e}"
                        logger.error(f"Error scraping — {msg}")
                        errors.append(msg)
                        step_error = str(e)

                    step_duration = (datetime.now(timezone.utc) - step_start).total_seconds()
                    self._status["step_results"].append({
                        "region": region,
                        "type": prop_type,
                        "count": step_count,
                        "duration_sec": round(step_duration, 1),
                        "error": step_error,
                    })

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

        # Mark listings not seen recently as stale/delisted
        self._status["current_phase"] = "lifecycle_sweep"
        try:
            stale = await mark_stale_listings(ttl_hours=self._ttl_hours)
            delisted = await mark_delisted(hours=48)
            if stale or delisted:
                logger.info(f"Lifecycle sweep: {stale} stale, {delisted} delisted")
        except Exception:
            logger.exception("Lifecycle sweep failed")

        # Refresh market data (interest rates, CPI) if stale
        self._status["current_phase"] = "refreshing_market"
        self._status["refresh_progress"]["market"]["status"] = "running"
        await self._refresh_market_data()

        # Refresh CMHC rent data if stale
        self._status["current_phase"] = "refreshing_rent"
        self._status["refresh_progress"]["rent"]["status"] = "running"
        await self._refresh_rent_data()

        # Refresh demographics data if stale
        self._status["current_phase"] = "refreshing_demographics"
        self._status["refresh_progress"]["demographics"]["status"] = "running"
        await self._refresh_demographics()

        # Refresh Montreal neighbourhood data (crime, permits, taxes)
        self._status["current_phase"] = "refreshing_neighbourhood"
        self._status["refresh_progress"]["neighbourhood"]["status"] = "running"
        await self._refresh_neighbourhood_data()

        # Run alert checker after scrape completes
        self._status["current_phase"] = "checking_alerts"
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

        # Enrich listings with detail-page data (gross_revenue, postal_code, etc.)
        self._status["current_phase"] = "enriching_details"
        self._status["enrichment_progress"]["details"]["phase"] = "running"
        await self._enrich_listing_details()

        # Enrich listings with Walk Scores
        self._status["current_phase"] = "enriching_walk_scores"
        self._status["enrichment_progress"]["walk_scores"]["phase"] = "running"
        await self._enrich_walk_scores()

        # Enrich listings with photo URLs (for listings not already covered by detail enrichment)
        self._status["current_phase"] = "enriching_photos"
        self._status["enrichment_progress"]["photos"]["phase"] = "running"
        await self._enrich_photo_urls()

        # Enrich listings with AI condition scores
        self._status["current_phase"] = "enriching_conditions"
        self._status["enrichment_progress"]["conditions"]["phase"] = "running"
        await self._enrich_condition_scores()

        # Validate and score data quality (runs LAST so all enrichment fields are available)
        self._status["current_phase"] = "validating_data"
        self._status["enrichment_progress"]["validation"]["phase"] = "running"
        await self._validate_data_quality()

        # Capture quality snapshot for historical tracking
        try:
            quality_snapshot = await get_data_quality_summary()
            ep = self._status["enrichment_progress"]
            quality_snapshot["enrichment_rates"] = {
                "details": round(ep["details"]["done"] / max(ep["details"]["total"], 1) * 100, 1),
                "walk_scores": round(ep["walk_scores"]["done"] / max(ep["walk_scores"]["total"], 1) * 100, 1),
                "photos": round(ep["photos"]["done"] / max(ep["photos"]["total"], 1) * 100, 1),
                "conditions": round(ep["conditions"]["done"] / max(ep["conditions"]["total"], 1) * 100, 1),
            }
        except Exception:
            logger.warning("Failed to capture quality snapshot", exc_info=True)
            quality_snapshot = None

        # Persist job history to database
        total_enriched = sum(
            self._status["enrichment_progress"][k]["done"]
            for k in ("details", "walk_scores", "photos", "conditions")
        )
        final_status = "failed" if errors else "completed"
        try:
            await insert_scrape_job(
                started_at=start_time,
                completed_at=datetime.now(timezone.utc),
                status=final_status,
                total_listings=total_stored,
                total_enriched=total_enriched,
                errors=errors,
                step_log=self._status["step_results"],
                duration_sec=round((datetime.now(timezone.utc) - start_time).total_seconds(), 1),
                quality_snapshot=quality_snapshot,
            )
        except Exception:
            logger.exception("Failed to persist scrape job to database")

        self._status["current_phase"] = None
        self._status["current_region"] = None
        self._status["current_type"] = None

    async def _enrich_listing_details(self):
        """Fetch detail pages to validate and correct ALL listing fields.

        The detail page is the authoritative source of truth. This step:
        1. Fetches the full listing page for each un-validated listing
        2. Extracts comprehensive data (revenue, address, units, etc.)
        3. Auto-corrects any search card fields that differ from detail page
        4. Logs all corrections for data quality monitoring

        Processes batches in a loop until all listings are enriched (capped at
        max_batches to prevent runaway cycles after schema changes).
        """
        from housemktanalyzr.collectors.centris import CentrisScraper

        batch_size = int(os.environ.get("DETAIL_ENRICH_BATCH_SIZE", 50))
        max_batches = int(os.environ.get("DETAIL_ENRICH_MAX_BATCHES", 20))
        delay = float(os.environ.get("DETAIL_ENRICH_DELAY", 1.5))

        total_enriched = 0
        total_failed = 0
        total_corrections = 0
        batch_num = 0

        async with CentrisScraper(request_interval=delay) as scraper:
            while batch_num < max_batches:
                batch_num += 1
                try:
                    listings = await get_listings_without_details(limit=batch_size)
                except Exception:
                    logger.exception("Failed to query listings for detail enrichment")
                    break

                if not listings:
                    if batch_num == 1:
                        logger.info("Detail enrichment: all listings already validated")
                    break

                logger.info(
                    f"Detail enrichment batch {batch_num}: "
                    f"{len(listings)} listings (delay={delay}s)"
                )
                self._status["enrichment_progress"]["details"]["total"] = (
                    total_enriched + total_failed + len(listings)
                )

                max_detail_retries = 2
                detail_retry_backoff = 3.0

                for item in listings:
                    detailed = None
                    for attempt in range(1, max_detail_retries + 1):
                        try:
                            detailed = await scraper.get_listing_details(
                                item["id"], url=item.get("url") or None
                            )
                            if detailed:
                                break
                            # got None — listing may be delisted, don't retry
                            break
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            if attempt < max_detail_retries:
                                logger.info(
                                    f"Detail fetch retry {attempt}/{max_detail_retries} "
                                    f"for {item['id']}: {e}"
                                )
                                await asyncio.sleep(detail_retry_backoff * attempt)
                            else:
                                logger.warning(
                                    f"Detail enrichment failed for {item['id']} "
                                    f"after {max_detail_retries} attempts: {e}"
                                )
                                detailed = None

                    try:
                        if detailed:
                            # Guard: if detail page returned but has zero
                            # useful data, don't stamp the sentinel — the page
                            # was likely empty or a redirect we didn't catch.
                            detail_fields = (
                                detailed.postal_code, detailed.sqft,
                                detailed.year_built, detailed.annual_taxes,
                                detailed.gross_revenue, detailed.municipal_assessment,
                                detailed.lot_sqft,
                            )
                            if not any(detail_fields) and detailed.address == "Unknown":
                                logger.warning(
                                    f"Detail enrichment for {item['id']} returned "
                                    f"empty data, skipping sentinel"
                                )
                                total_failed += 1
                                self._status["enrichment_progress"]["details"]["done"] = total_enriched
                                self._status["enrichment_progress"]["details"]["failed"] = total_failed
                                continue

                            # Build fields dict: detail page is authoritative
                            fields = {
                                # Detail-only fields (not on search cards)
                                "gross_revenue": detailed.gross_revenue,
                                "total_expenses": detailed.total_expenses,
                                "net_income": detailed.net_income,
                                "postal_code": detailed.postal_code,
                                "lot_sqft": detailed.lot_sqft,
                                "year_built": detailed.year_built,
                                "municipal_assessment": detailed.municipal_assessment,
                                "annual_taxes": detailed.annual_taxes,
                                "sqft": detailed.sqft,
                                # Validation timestamp
                                "detail_enriched_at": datetime.now(timezone.utc).isoformat(),
                            }
                            # Photos
                            if detailed.photo_urls:
                                fields["photo_urls"] = detailed.photo_urls

                            # Auto-correct search card fields from detail page
                            # Only override when detail page has a real value (not default)
                            if detailed.address and detailed.address != "Unknown":
                                fields["address"] = detailed.address
                            if detailed.city and detailed.city != "Montreal":
                                fields["city"] = detailed.city
                            if detailed.units and detailed.units > 1:
                                fields["units"] = detailed.units
                            if detailed.bedrooms and detailed.bedrooms > 0:
                                fields["bedrooms"] = detailed.bedrooms
                            if detailed.bathrooms and detailed.bathrooms > 0:
                                fields["bathrooms"] = detailed.bathrooms
                            if detailed.property_type:
                                fields["property_type"] = detailed.property_type.value
                            if detailed.price and detailed.price > 0:
                                fields["price"] = detailed.price

                            # Also update indexed columns when corrected
                            column_updates = {}
                            if "city" in fields and fields["city"]:
                                column_updates["city"] = fields["city"]
                            if "property_type" in fields:
                                column_updates["property_type"] = fields["property_type"]

                            result = await update_listing_details(
                                item["id"], fields, column_updates=column_updates
                            )
                            if result.get("corrections"):
                                total_corrections += len(result["corrections"])
                                logger.info(
                                    f"Auto-corrected {item['id']}: "
                                    + "; ".join(result["corrections"][:5])
                                )
                            total_enriched += 1
                        else:
                            total_failed += 1
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.warning(f"Detail enrichment failed for {item['id']}: {e}")
                        total_failed += 1
                    self._status["enrichment_progress"]["details"]["done"] = total_enriched
                    self._status["enrichment_progress"]["details"]["failed"] = total_failed

                # If we got fewer than batch_size, we've processed everything
                if len(listings) < batch_size:
                    break

        self._status["enrichment_progress"]["details"]["phase"] = "done"
        self._status["enrichment_progress"]["details"]["corrections"] = total_corrections
        logger.info(
            f"Detail enrichment done: {total_enriched} enriched, "
            f"{total_failed} failed, {total_corrections} corrections "
            f"across {batch_num} batch(es)"
        )

    async def _validate_data_quality(self):
        """Run validation pipeline on all active listings.

        Applies corrections, sanity checks, and quality scoring via
        data_validator.validate_listing().
        """
        from .data_validator import validate_listing
        from .db import get_pool

        pool = get_pool()
        now = datetime.now(timezone.utc)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, data FROM properties WHERE expires_at > $1",
                now,
            )

        total = len(rows)
        corrected = 0
        flagged = 0
        self._status["enrichment_progress"]["validation"]["total"] = total

        for row in rows:
            data = json.loads(row["data"])
            data = validate_listing(data)
            quality = data.get("_quality", {})
            if quality.get("corrections"):
                corrected += 1
            if quality.get("flags"):
                flagged += 1
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE properties SET data = $1::jsonb WHERE id = $2",
                    json.dumps(data), row["id"],
                )

        self._status["enrichment_progress"]["validation"].update({
            "corrected": corrected,
            "flagged": flagged,
            "phase": "done",
        })
        logger.info(
            f"Data validation: {total} listings, "
            f"{corrected} corrected, {flagged} flagged"
        )

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
            self._status["enrichment_progress"]["walk_scores"]["phase"] = "done"
            return

        self._status["enrichment_progress"]["walk_scores"]["total"] = len(listings)
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
            self._status["enrichment_progress"]["walk_scores"]["done"] = enriched
            self._status["enrichment_progress"]["walk_scores"]["failed"] = failed

            await asyncio.sleep(delay)

        self._status["enrichment_progress"]["walk_scores"]["phase"] = "done"
        logger.info(f"Walk Score enrichment done: {enriched} enriched, {failed} failed")

    async def _enrich_photo_urls(self):
        """Fetch detail pages to extract photo URLs for listings missing them."""
        from housemktanalyzr.collectors.centris import CentrisScraper

        batch_size = int(os.environ.get("PHOTO_BATCH_SIZE", 30))
        delay = float(os.environ.get("PHOTO_FETCH_DELAY", 1.5))

        try:
            listings = await get_listings_without_photos(limit=batch_size)
        except Exception:
            logger.exception("Failed to query listings for photo enrichment")
            return

        if not listings:
            logger.info("Photos: all listings already have photos")
            self._status["enrichment_progress"]["photos"]["phase"] = "done"
            return

        self._status["enrichment_progress"]["photos"]["total"] = len(listings)
        logger.info(f"Photos: fetching detail pages for {len(listings)} listings")
        enriched = 0
        failed = 0

        async with CentrisScraper(request_interval=delay) as scraper:
            for item in listings:
                try:
                    detailed = await scraper.get_listing_details(
                        item["id"], url=item.get("url") or None
                    )
                    if detailed and detailed.photo_urls:
                        await update_photo_urls(item["id"], detailed.photo_urls)
                        enriched += 1
                    else:
                        # Mark with empty list so we don't retry
                        await update_photo_urls(item["id"], [])
                        failed += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Photo fetch failed for {item['id']}: {e}")
                    # Set sentinel so we don't retry on crash/timeout failures
                    try:
                        await update_photo_urls(item["id"], [])
                    except Exception:
                        pass
                    failed += 1
                self._status["enrichment_progress"]["photos"]["done"] = enriched
                self._status["enrichment_progress"]["photos"]["failed"] = failed

        self._status["enrichment_progress"]["photos"]["phase"] = "done"
        logger.info(f"Photo enrichment done: {enriched} enriched, {failed} failed")

    async def _enrich_condition_scores(self):
        """Score property condition using Gemini for listings with photos."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            logger.info("Condition scoring skipped: GEMINI_API_KEY not set")
            self._status["enrichment_progress"]["conditions"]["phase"] = "done"
            return

        from housemktanalyzr.enrichment.condition_scorer import score_property_condition

        batch_size = int(os.environ.get("CONDITION_BATCH_SIZE", 25))
        delay = float(os.environ.get("CONDITION_SCORE_DELAY", 6.0))

        try:
            listings = await get_listings_without_condition_score(limit=batch_size)
        except Exception:
            logger.exception("Failed to query listings for condition scoring")
            return

        if not listings:
            logger.info("Condition scoring: all eligible listings already scored")
            self._status["enrichment_progress"]["conditions"]["phase"] = "done"
            return

        self._status["enrichment_progress"]["conditions"]["total"] = len(listings)
        logger.info(
            f"Condition scoring: processing {len(listings)} listings "
            f"(delay={delay}s, ~{len(listings) * delay / 60:.1f}min)"
        )
        scored = 0
        failed = 0

        for item in listings:
            try:
                result = await score_property_condition(
                    photo_urls=item["photo_urls"],
                    property_type=item.get("property_type", "property"),
                    city=item.get("city", "Montreal"),
                    year_built=item.get("year_built"),
                )
                if result:
                    await update_condition_score(
                        listing_id=item["id"],
                        condition_score=result.overall_score,
                        condition_details={
                            "kitchen": result.kitchen_score,
                            "bathroom": result.bathroom_score,
                            "floors": result.floors_score,
                            "exterior": result.exterior_score,
                            "renovation_needed": result.renovation_needed,
                            "notes": result.notes,
                        },
                    )
                    scored += 1
                else:
                    failed += 1
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Condition scoring failed for {item['id']}: {e}")
                failed += 1
            self._status["enrichment_progress"]["conditions"]["done"] = scored
            self._status["enrichment_progress"]["conditions"]["failed"] = failed

            await asyncio.sleep(delay)

        self._status["enrichment_progress"]["conditions"]["phase"] = "done"
        logger.info(f"Condition scoring done: {scored} scored, {failed} failed")

    async def _refresh_market_data(self):
        """Fetch latest market rates from Bank of Canada if data is stale."""
        from housemktanalyzr.enrichment.market_data import BankOfCanadaClient, BOC_SERIES

        refresh_hours = float(os.environ.get("MARKET_DATA_REFRESH_HOURS", 24))

        # Check if data is fresh enough
        try:
            age = await get_market_data_age("boc_mortgage_5yr")
            if age is not None and age < refresh_hours:
                logger.info(f"Market data: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                self._status["refresh_progress"]["market"]["status"] = "skipped"
                return
        except Exception:
            logger.exception("Failed to check market data age")

        logger.info("Market data: refreshing from Bank of Canada")
        client = BankOfCanadaClient()

        series_map = {
            "policy_rate": "boc_policy_rate",
            "mortgage_5yr": "boc_mortgage_5yr",
            "mortgage_3yr": "boc_mortgage_3yr",
            "mortgage_1yr": "boc_mortgage_1yr",
            "cpi": "boc_cpi",
            "prime_rate": "boc_prime_rate",
        }

        total_upserted = 0
        try:
            rates = await client.get_all_rates(lookback_years=5)

            for name, history in rates.items():
                db_series_id = series_map.get(name)
                if not db_series_id:
                    continue

                observations = [
                    {"date": obs.date, "value": obs.value}
                    for obs in history.observations
                ]
                count = await upsert_market_data(
                    series_id=db_series_id,
                    observations=observations,
                    source="bank_of_canada",
                )
                total_upserted += count

            logger.info(f"Market data: upserted {total_upserted} observations")
            self._status["refresh_progress"]["market"]["status"] = "done"

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Market data refresh failed")
            self._status["refresh_progress"]["market"]["status"] = "failed"
        finally:
            await client.close()

    async def _refresh_rent_data(self):
        """Fetch CMHC rent and vacancy data for all active CMAs if stale."""
        from housemktanalyzr.enrichment.cmhc_client import CMHCClient
        from .constants import CMA_CONFIG, get_active_cmas

        refresh_hours = float(os.environ.get("RENT_DATA_REFRESH_HOURS", 168))  # weekly

        try:
            age = await get_rent_data_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Rent data: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                self._status["refresh_progress"]["rent"]["status"] = "skipped"
                return
        except Exception:
            logger.exception("Failed to check rent data age")

        bed_attr_map = {
            "bachelor": "bachelor",
            "1br": "one_br",
            "2br": "two_br",
            "3br+": "three_br_plus",
        }

        active_cmas = get_active_cmas()
        logger.info(f"Rent data: refreshing from CMHC for {len(active_cmas)} CMA(s): {active_cmas}")

        total_upserted = 0
        for cma_key in active_cmas:
            config = CMA_CONFIG.get(cma_key)
            if not config:
                logger.warning(f"Rent data: no CMA_CONFIG for '{cma_key}', skipping")
                continue

            client = CMHCClient(cma_key)
            try:
                # Fetch current year snapshot (rents + vacancy by zone)
                snapshot = await client.get_snapshot()

                rows = []
                for rent_data in snapshot.rents:
                    for bed_key, attr in bed_attr_map.items():
                        val = getattr(rent_data, attr, None)
                        if val is not None:
                            rows.append({
                                "zone": rent_data.zone,
                                "bedroom_type": bed_key,
                                "year": rent_data.year,
                                "avg_rent": val,
                            })

                for vac_data in snapshot.vacancies:
                    for bed_key, attr in bed_attr_map.items():
                        val = getattr(vac_data, attr, None)
                        if val is not None:
                            found = False
                            for row in rows:
                                if row["zone"] == vac_data.zone and row["bedroom_type"] == bed_key and row["year"] == vac_data.year:
                                    row["vacancy_rate"] = val
                                    found = True
                                    break
                            if not found:
                                rows.append({
                                    "zone": vac_data.zone,
                                    "bedroom_type": bed_key,
                                    "year": vac_data.year,
                                    "vacancy_rate": val,
                                })

                if rows:
                    total_upserted += await upsert_rent_data_batch(rows)

                # Also fetch historical CMA-level rents + vacancy for trend analysis
                fallback_zone = config["fallback_zone"]
                historical = await client.get_historical_rents()
                hist_rows: dict[tuple[str, int], dict] = {}
                for h in historical:
                    for bed_key, attr in bed_attr_map.items():
                        val = getattr(h, attr, None)
                        if val is not None:
                            key = (bed_key, h.year)
                            hist_rows[key] = {
                                "zone": fallback_zone,
                                "bedroom_type": bed_key,
                                "year": h.year,
                                "avg_rent": val,
                            }

                historical_vac = await client.get_historical_vacancy()
                for hv in historical_vac:
                    for bed_key, attr in bed_attr_map.items():
                        val = hv.get(attr)
                        if val is not None:
                            key = (bed_key, hv["year"])
                            if key in hist_rows:
                                hist_rows[key]["vacancy_rate"] = val
                            else:
                                hist_rows[key] = {
                                    "zone": fallback_zone,
                                    "bedroom_type": bed_key,
                                    "year": hv["year"],
                                    "vacancy_rate": val,
                                }

                if hist_rows:
                    total_upserted += await upsert_rent_data_batch(list(hist_rows.values()))

                logger.info(f"Rent data ({cma_key}): upserted for this CMA")

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(f"Rent data refresh failed for CMA '{cma_key}'")
            finally:
                await client.close()

        logger.info(f"Rent data: upserted {total_upserted} rows total across {len(active_cmas)} CMA(s)")
        self._status["refresh_progress"]["rent"]["status"] = "done" if total_upserted > 0 else "failed"

    async def _refresh_demographics(self):
        """Fetch StatCan census demographics if stale (refreshes monthly)."""
        from housemktanalyzr.enrichment.demographics import StatCanCensusClient

        refresh_hours = float(os.environ.get("DEMOGRAPHICS_REFRESH_HOURS", 720))  # ~30 days

        try:
            age = await get_demographics_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Demographics: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                self._status["refresh_progress"]["demographics"]["status"] = "skipped"
                return
        except Exception:
            logger.exception("Failed to check demographics age")

        logger.info("Demographics: refreshing from StatCan Census")
        client = StatCanCensusClient()

        try:
            profiles = await client.get_demographics()

            rows = [
                {
                    "csd_code": p.csd_code,
                    "municipality": p.municipality,
                    "population": p.population,
                    "population_2016": p.population_2016,
                    "pop_change_pct": p.pop_change_pct,
                    "avg_household_size": p.avg_household_size,
                    "total_households": p.total_households,
                    "median_household_income": p.median_household_income,
                    "median_after_tax_income": p.median_after_tax_income,
                    "avg_household_income": p.avg_household_income,
                    "source": "statcan_2021",
                }
                for p in profiles
            ]

            count = await upsert_demographics_batch(rows)
            logger.info(f"Demographics: upserted {count} municipality profiles")
            self._status["refresh_progress"]["demographics"]["status"] = "done"

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Demographics refresh failed")
            self._status["refresh_progress"]["demographics"]["status"] = "failed"
        finally:
            await client.close()

    async def _refresh_neighbourhood_data(self):
        """Fetch neighbourhood data from all CMA sources if stale (refreshes weekly)."""
        refresh_hours = float(os.environ.get("NEIGHBOURHOOD_REFRESH_HOURS", 168))  # weekly

        try:
            age = await get_neighbourhood_stats_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Neighbourhood data: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                self._status["refresh_progress"]["neighbourhood"]["status"] = "skipped"
                return
        except Exception:
            logger.exception("Failed to check neighbourhood data age")

        logger.info("Neighbourhood data: refreshing from all sources")

        # Each source is independent — one failure doesn't block the others.
        try:
            await self._refresh_montreal_neighbourhood()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Montreal neighbourhood data refresh failed")

        try:
            await self._refresh_sherbrooke_neighbourhood()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Sherbrooke neighbourhood data refresh failed")

        try:
            await self._refresh_quebec_city_neighbourhood()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Quebec City neighbourhood data refresh failed")

        self._status["refresh_progress"]["neighbourhood"]["status"] = "done"

        # Check for stale hardcoded data that needs manual update.
        self._check_neighbourhood_data_staleness()

    def _check_neighbourhood_data_staleness(self):
        """Log warnings when hardcoded neighbourhood data needs updating.

        Populates self._status["data_warnings"] for the status dashboard.
        """
        from datetime import date as date_cls
        current_year = date_cls.today().year
        warnings: list[dict[str, str]] = []

        # Quebec City: SPVQ crime data (updated manually from annual PDF report)
        try:
            from housemktanalyzr.enrichment.quebec_city_data import (
                SPVQ_CRIME_DATA, _TAX_RATES_BY_SECTOR as QC_TAX_RATES,
            )
            latest_spvq = max(SPVQ_CRIME_DATA.keys()) if SPVQ_CRIME_DATA else 0
            if latest_spvq < current_year - 1:
                msg = (
                    f"Quebec City SPVQ crime data latest year is {latest_spvq}, "
                    f"expected {current_year - 1}"
                )
                logger.warning(f"STALE DATA: {msg}")
                warnings.append({
                    "source": "Quebec City crime (SPVQ)",
                    "message": msg,
                    "action": (
                        f"Update SPVQ_CRIME_DATA in quebec_city_data.py from "
                        f"rapport_annuel_police_{current_year - 1}.pdf"
                    ),
                })
            latest_qc_tax = max(QC_TAX_RATES.keys()) if QC_TAX_RATES else 0
            if latest_qc_tax < current_year:
                msg = (
                    f"Quebec City tax rate latest year is {latest_qc_tax}, "
                    f"expected {current_year}"
                )
                logger.warning(f"STALE DATA: {msg}")
                warnings.append({
                    "source": "Quebec City tax rates",
                    "message": msg,
                    "action": "Update _TAX_RATES_BY_SECTOR in quebec_city_data.py",
                })
        except Exception:
            logger.debug("Could not check Quebec City data staleness", exc_info=True)

        # Sherbrooke: tax rates are automated via MAMH CSV, but check
        # fallback values in case MAMH becomes unavailable.
        try:
            from housemktanalyzr.enrichment.sherbrooke_data import (
                _TAX_RATES_FALLBACK as SH_TAX_FALLBACK,
            )
            latest_sh_tax = max(SH_TAX_FALLBACK.keys()) if SH_TAX_FALLBACK else 0
            if latest_sh_tax < current_year:
                msg = (
                    f"Sherbrooke tax rate fallback latest year is {latest_sh_tax}, "
                    f"expected {current_year} (primary source: MAMH CSV, automated)"
                )
                logger.info(f"STALE FALLBACK: {msg}")
                warnings.append({
                    "source": "Sherbrooke tax rates (fallback)",
                    "message": msg,
                    "action": "Update _TAX_RATES_FALLBACK in sherbrooke_data.py (low priority — MAMH is automated)",
                })
        except Exception:
            logger.debug("Could not check Sherbrooke data staleness", exc_info=True)

        self._status["data_warnings"] = warnings
        if warnings:
            logger.info(f"Data staleness check: {len(warnings)} warning(s) found")

    async def _refresh_montreal_neighbourhood(self):
        """Fetch Montreal Open Data (crime, permits, taxes)."""
        from housemktanalyzr.enrichment.montreal_data import MontrealOpenDataClient

        logger.info("Montreal neighbourhood: fetching crime, permits, taxes")
        client = MontrealOpenDataClient()
        try:
            from datetime import date as date_cls
            current_year = date_cls.today().year - 1

            stats_list = await client.get_neighbourhood_stats()

            rows = []
            for stats in stats_list:
                row = {
                    "borough": stats.borough,
                    "year": current_year,
                    "source": "montreal_open_data",
                    "safety_score": stats.safety_score,
                    "gentrification_signal": stats.gentrification_signal,
                }
                if stats.crime:
                    row.update({
                        "crime_count": stats.crime.total_crimes,
                        "violent_crimes": stats.crime.violent_crimes,
                        "property_crimes": stats.crime.property_crimes,
                        "crime_change_pct": stats.crime.year_over_year_change_pct,
                    })
                if stats.permits:
                    row.update({
                        "permit_count": stats.permits.total_permits,
                        "permit_transform_count": stats.permits.transform_permits,
                        "permit_construction_count": stats.permits.construction_permits,
                        "permit_demolition_count": stats.permits.demolition_permits,
                        "permit_total_cost": stats.permits.total_cost,
                    })
                if stats.tax:
                    row.update({
                        "tax_rate_residential": stats.tax.residential_rate,
                        "tax_rate_total": stats.tax.total_tax_rate,
                    })
                rows.append(row)

            if rows:
                count = await upsert_neighbourhood_stats_batch(rows)
                logger.info(f"Montreal neighbourhood: upserted {count} borough stats")
            else:
                logger.warning("Montreal neighbourhood: no results from Open Data")

            # Fetch multi-year tax history for trend analysis
            try:
                multi_year_taxes = await client.get_tax_rates_multi_year(
                    current_year - 4, current_year
                )
                if multi_year_taxes:
                    tax_rows = [
                        {
                            "borough": t.borough,
                            "year": t.year,
                            "residential_rate": t.residential_rate,
                            "total_tax_rate": t.total_tax_rate,
                            "source": "montreal_open_data",
                        }
                        for t in multi_year_taxes
                    ]
                    tax_count = await upsert_tax_rate_history_batch(tax_rows)
                    logger.info(f"Tax rate history: upserted {tax_count} borough/year records")
            except Exception:
                logger.exception("Tax rate history fetch failed (non-blocking)")
        finally:
            await client.close()

    async def _refresh_sherbrooke_neighbourhood(self):
        """Fetch Sherbrooke crime data from ArcGIS."""
        from housemktanalyzr.enrichment.sherbrooke_data import SherbrookeCrimeClient

        logger.info("Sherbrooke neighbourhood: fetching crime data")
        client = SherbrookeCrimeClient()
        try:
            rows = await client.get_neighbourhood_rows()
            if rows:
                count = await upsert_neighbourhood_stats_batch(rows)
                logger.info(f"Sherbrooke neighbourhood: upserted {count} arrondissement stats")
            else:
                logger.warning("Sherbrooke neighbourhood: no results")
        finally:
            await client.close()

    async def _refresh_quebec_city_neighbourhood(self):
        """Fetch Quebec City permit data from Données Québec."""
        from housemktanalyzr.enrichment.quebec_city_data import QuebecCityPermitsClient

        logger.info("Quebec City neighbourhood: fetching permit data")
        client = QuebecCityPermitsClient()
        try:
            rows = await client.get_neighbourhood_rows()
            if rows:
                count = await upsert_neighbourhood_stats_batch(rows)
                logger.info(f"Quebec City neighbourhood: upserted {count} arrondissement stats")
            else:
                logger.warning("Quebec City neighbourhood: no results")
        finally:
            await client.close()
