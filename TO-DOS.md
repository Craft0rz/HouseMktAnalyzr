# TO-DOS

## Actual Rent vs Average Rent Analysis - 2026-02-08 14:37

- **Add actual vs average rent analysis** - Compare listing-reported gross revenue against CMHC average rents to flag under/over-rented properties. **Problem:** The scraper collects gross_revenue from Centris detail pages and CMHC average rents by zone/bedroom type are already fetched via `CMHCClient.get_rents_by_zone()`, but there's no analysis that compares the two to identify rent upside or downside risk. **Files:** `src/housemktanalyzr/enrichment/cmhc.py`, `src/housemktanalyzr/enrichment/cmhc_client.py:225-248`, `src/housemktanalyzr/analysis/calculator.py`, `src/housemktanalyzr/models/property.py`. **Solution:** For each listing with reported revenue, compute expected rent from CMHC zone data (matched by postal code/city), then surface a rent delta metric (actual vs market average) in the analysis pipeline and dashboard.
