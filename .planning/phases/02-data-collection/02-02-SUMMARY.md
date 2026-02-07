# Summary: 02-02 Data Collector Framework

**One-liner**: Built a flexible data collection framework with pluggable sources and implemented Centris.ca web scraper as the initial data source.

## Accomplishments

- Created abstract `DataSource` base class defining the plugin interface for all data sources
- Implemented `CentrisScraper` with:
  - Async HTTP requests using httpx
  - HTML parsing with BeautifulSoup4
  - Rate limiting (1 request/second minimum)
  - Exponential backoff on failures
  - CAPTCHA detection (raises exception, doesn't retry)
  - Mapping to PropertyListing model
  - Region and property type filtering
- Built `DataCollector` orchestrator with:
  - Auto-discovery of available data sources
  - Source priority ordering (lower number = higher priority)
  - Automatic fallback on source failure
  - In-memory caching with configurable TTL (default 5 minutes)
  - Logging of which source was used
  - Async context manager support
- Added custom exception classes: `DataSourceError`, `RateLimitError`, `CaptchaError`
- Added BeautifulSoup4 to project dependencies

## Files Created/Modified

### Created
| File | Purpose |
|------|---------|
| `src/housemktanalyzr/collectors/__init__.py` | Module exports and documentation |
| `src/housemktanalyzr/collectors/base.py` | DataSource ABC and exception classes |
| `src/housemktanalyzr/collectors/centris.py` | CentrisScraper implementation |
| `src/housemktanalyzr/collectors/collector.py` | DataCollector orchestrator |

### Modified
| File | Change |
|------|--------|
| `pyproject.toml` | Added `beautifulsoup4>=4.12.0` dependency |

## Decisions Made

1. **Scraping over API**: Started with web scraping since it works immediately without broker authorization, while keeping architecture open for API integrations (Houski, Repliers) later

2. **httpx for HTTP**: Chose httpx over requests for native async support, aligning with async architecture throughout

3. **Priority-based fallback**: DataCollector tries sources in priority order and falls back on failure, providing resilience

4. **In-memory cache**: Implemented simple dict-based caching with TTL to reduce redundant requests; can be upgraded to Redis/disk later if needed

5. **Exception hierarchy**: Created specific exceptions (CaptchaError, RateLimitError) to allow callers to handle different failure modes appropriately

6. **Auto-discovery pattern**: DataCollector automatically discovers and registers available sources, making it easy to add new sources without code changes

## Issues Encountered

None - implementation proceeded without blockers.

## Verification Results

All checks passed:
- `pip install -e .` - SUCCESS
- `from housemktanalyzr.collectors import DataSource, DataCollector, CentrisScraper` - SUCCESS
- `DataCollector()` instantiation - SUCCESS
- `dc.get_available_sources()` returns `['centris']` - SUCCESS
- `CentrisScraper` implements all `DataSource` methods - SUCCESS

## Next Step

Proceed to **02-03: Supplementary Data Sources** to add CMHC rental data and Quebec municipal assessment data for enriching property listings with rental estimates and assessment values.
