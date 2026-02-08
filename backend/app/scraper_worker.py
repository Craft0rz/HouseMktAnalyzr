"""Background scraper worker that populates the DB with all Centris listings."""

import asyncio
import logging
import os
from datetime import datetime, timezone

from .constants import SCRAPE_MATRIX
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

        # Refresh market data (interest rates, CPI) if stale
        await self._refresh_market_data()

        # Refresh CMHC rent data if stale
        await self._refresh_rent_data()

        # Refresh demographics data if stale
        await self._refresh_demographics()

        # Refresh Montreal neighbourhood data (crime, permits, taxes)
        await self._refresh_neighbourhood_data()

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

        # Enrich listings with detail-page data (gross_revenue, postal_code, etc.)
        await self._enrich_listing_details()

        # Enrich listings with Walk Scores
        await self._enrich_walk_scores()

        # Enrich listings with photo URLs (for listings not already covered by detail enrichment)
        await self._enrich_photo_urls()

        # Enrich listings with AI condition scores
        await self._enrich_condition_scores()

    async def _enrich_listing_details(self):
        """Fetch detail pages to fill in gross_revenue, postal_code, and other fields.

        Search cards don't include revenue, postal code, lot size, year built,
        assessment, or taxes. This step fetches the full listing page and merges
        all available fields into the cached JSONB data.
        """
        from housemktanalyzr.collectors.centris import CentrisScraper

        batch_size = int(os.environ.get("DETAIL_ENRICH_BATCH_SIZE", 50))
        delay = float(os.environ.get("DETAIL_ENRICH_DELAY", 1.5))

        try:
            listings = await get_listings_without_details(limit=batch_size)
        except Exception:
            logger.exception("Failed to query listings for detail enrichment")
            return

        if not listings:
            logger.info("Detail enrichment: all listings already have details")
            return

        logger.info(f"Detail enrichment: fetching {len(listings)} detail pages (delay={delay}s)")
        enriched = 0
        failed = 0

        async with CentrisScraper(request_interval=delay) as scraper:
            for item in listings:
                try:
                    detailed = await scraper.get_listing_details(
                        item["id"], url=item.get("url") or None
                    )
                    if detailed:
                        fields = {
                            "gross_revenue": detailed.gross_revenue,
                            "postal_code": detailed.postal_code,
                            "lot_sqft": detailed.lot_sqft,
                            "year_built": detailed.year_built,
                            "municipal_assessment": detailed.municipal_assessment,
                            "annual_taxes": detailed.annual_taxes,
                            "sqft": detailed.sqft,
                        }
                        # Also grab photos if available
                        if detailed.photo_urls:
                            fields["photo_urls"] = detailed.photo_urls

                        await update_listing_details(item["id"], fields)
                        enriched += 1
                    else:
                        failed += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Detail enrichment failed for {item['id']}: {e}")
                    failed += 1

        logger.info(f"Detail enrichment done: {enriched} enriched, {failed} failed")

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
            return

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
                    failed += 1

        logger.info(f"Photo enrichment done: {enriched} enriched, {failed} failed")

    async def _enrich_condition_scores(self):
        """Score property condition using Gemini for listings with photos."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            logger.info("Condition scoring skipped: GEMINI_API_KEY not set")
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
            return

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

            await asyncio.sleep(delay)

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

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Market data refresh failed")
        finally:
            await client.close()

    async def _refresh_rent_data(self):
        """Fetch CMHC rent and vacancy data if stale (refreshes weekly)."""
        from housemktanalyzr.enrichment.cmhc_client import CMHCClient

        refresh_hours = float(os.environ.get("RENT_DATA_REFRESH_HOURS", 168))  # weekly

        try:
            age = await get_rent_data_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Rent data: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                return
        except Exception:
            logger.exception("Failed to check rent data age")

        logger.info("Rent data: refreshing from CMHC")
        client = CMHCClient("montreal")

        bed_attr_map = {
            "bachelor": "bachelor",
            "1br": "one_br",
            "2br": "two_br",
            "3br+": "three_br_plus",
        }

        total_upserted = 0
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
                        # Find matching row or create new one
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

            # Also fetch historical CMA-level rents for trend analysis
            historical = await client.get_historical_rents()
            hist_rows = []
            for h in historical:
                for bed_key, attr in bed_attr_map.items():
                    val = getattr(h, attr, None)
                    if val is not None:
                        hist_rows.append({
                            "zone": "Montreal CMA Total",
                            "bedroom_type": bed_key,
                            "year": h.year,
                            "avg_rent": val,
                        })
            if hist_rows:
                total_upserted += await upsert_rent_data_batch(hist_rows)

            logger.info(f"Rent data: upserted {total_upserted} rows")

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Rent data refresh failed")
        finally:
            await client.close()

    async def _refresh_demographics(self):
        """Fetch StatCan census demographics if stale (refreshes monthly)."""
        from housemktanalyzr.enrichment.demographics import StatCanCensusClient

        refresh_hours = float(os.environ.get("DEMOGRAPHICS_REFRESH_HOURS", 720))  # ~30 days

        try:
            age = await get_demographics_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Demographics: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
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

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Demographics refresh failed")
        finally:
            await client.close()

    async def _refresh_neighbourhood_data(self):
        """Fetch Montreal Open Data (crime, permits, taxes) if stale (refreshes weekly)."""
        from housemktanalyzr.enrichment.montreal_data import MontrealOpenDataClient

        refresh_hours = float(os.environ.get("NEIGHBOURHOOD_REFRESH_HOURS", 168))  # weekly

        try:
            age = await get_neighbourhood_stats_age()
            if age is not None and age < refresh_hours:
                logger.info(f"Neighbourhood data: fresh ({age:.1f}h old, threshold {refresh_hours}h)")
                return
        except Exception:
            logger.exception("Failed to check neighbourhood data age")

        logger.info("Neighbourhood data: refreshing from Montreal Open Data")
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
                logger.info(f"Neighbourhood data: upserted {count} borough stats")
            else:
                logger.warning("Neighbourhood data: no results from Montreal Open Data")

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Neighbourhood data refresh failed")
        finally:
            await client.close()
