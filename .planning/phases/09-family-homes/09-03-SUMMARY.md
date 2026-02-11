# 09-03 Summary: Quebec Geo Data Enrichment

**One-liner**: Integrated Quebec government geo data sources (school proximity, flood zones, parks) into the family home scoring pipeline with background scraper enrichment for HOUSE listings.

## Accomplishments

- **Quebec geo data fetcher module** (`quebec_geo.py`) created with three async functions:
  - `fetch_nearby_schools()` — Queries Quebec MEES ArcGIS endpoint for schools within 2km, returns name/type/distance/language
  - `check_flood_zone()` — Queries CEHQ ESRI REST API to detect flood zone designation
  - `fetch_nearby_parks()` — Montreal Open Data for Montreal area, OSM Overpass API fallback for other Quebec regions
  - `haversine_distance()` helper for coordinate distance calculations
  - In-memory cache keyed by `(round(lat,3), round(lon,3))` to avoid repeated API calls for nearby properties
  - httpx.AsyncClient with 5-second timeouts on all external calls
  - Graceful error handling: all functions return None on failure, never crash the caller

- **Family scoring pipeline integration** (analysis.py + family_scorer.py):
  - New `_fetch_geo_data()` helper that checks listing `raw_data.geo_enrichment` for pre-enriched data before making live API calls
  - `family-score` endpoint now calls geo functions in parallel with location data via `asyncio.gather()`
  - `family-score-batch` endpoint uses `asyncio.Semaphore(10)` for concurrency limiting across all geo API calls
  - School proximity scoring updated to 5-tier system: <=500m (10pts), <=1000m (7pts), <=1500m (4pts), <=2000m (2pts), >2000m (0pts)
  - Parks scoring now receives real data: >=3 parks (6pts), >=2 (4pts), >=1 (2pts), 0 (0pts)
  - Flood zone flag set from CEHQ API data (risk disclosure, no score impact)

- **Scraper worker geo enrichment phase** added:
  - New `_enrich_geo_data()` method processes up to 50 HOUSE listings per cycle
  - 1-second delay between API calls to be respectful of external services
  - Stores results in listing `raw_data` under `geo_enrichment` key with structure: schools, nearest_elementary_m, flood_zone, flood_zone_type, park_count_1km, nearest_park_m, enriched_at
  - Runs after conditions enrichment, before data validation
  - Progress tracked in enrichment_progress status dict
  - Pre-enriched listings skip live API calls in scoring endpoints (fast path)

- **DB helper functions** added:
  - `get_houses_without_geo_enrichment()` — Queries HOUSE listings with coordinates but no geo_enrichment data
  - `update_geo_enrichment()` — Merges geo data into listing JSONB under geo_enrichment key

## Files Created

- `src/housemktanalyzr/enrichment/quebec_geo.py` — Quebec geo data fetcher module (schools, flood zones, parks)

## Files Modified

- `src/housemktanalyzr/analysis/family_scorer.py` — Updated school proximity scoring to 5-tier system, removed placeholder comments
- `backend/app/routers/analysis.py` — Added geo data imports, `_fetch_geo_data()` helper, `_geo_semaphore`, updated both family-score endpoints
- `backend/app/scraper_worker.py` — Added geo enrichment imports, `_enrich_geo_data()` method, progress tracking, pipeline integration
- `backend/app/db.py` — Added `get_houses_without_geo_enrichment()` and `update_geo_enrichment()` functions

## Decisions Made

1. **Pre-enrichment fast path**: Scoring endpoints check `raw_data.geo_enrichment` before making live API calls, ensuring fast scoring for enriched listings
2. **Montreal bounding box**: Used rough lat/lon bounding box (45.40-45.70, -73.97 to -73.47) to determine Montreal vs non-Montreal for park data source selection
3. **OSM fallback**: Montreal Open Data is primary for parks in Montreal; OSM Overpass API serves as universal fallback for all other Quebec regions
4. **Cache precision**: Used 3 decimal places (~111m) for coordinate rounding in cache keys — properties within the same block share cached results
5. **Semaphore scope**: Single `asyncio.Semaphore(10)` at module level shared by all geo API calls across batch scoring requests
6. **Flood zone as flag only**: Flood zone data sets the boolean flag on FamilyHomeMetrics but does not penalize the score (risk disclosure per plan spec)

## Verification Results

- `quebec_geo.py` — AST parse: OK
- `family_scorer.py` — AST parse: OK
- `analysis.py` — AST parse: OK
- `scraper_worker.py` — AST parse: OK
- `db.py` — AST parse: OK

## Issues Encountered

None. All three tasks completed without blockers.

## Deviations

- **Added 1500m tier to school scoring**: The existing code had 500/1000/2000 tiers; updated to match plan's 500/1000/1500/2000 five-tier specification
- **Added db.py functions**: Plan did not explicitly mention DB helper functions, but they were necessary for the scraper worker to query and update listings (auto-fix blocker)
