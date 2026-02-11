# 09-02 Summary: Frontend Houses Section

**One-liner**: Added a dedicated /houses page with family-oriented card grid, HouseDetail slide-over component with 3-pillar score breakdown and cost-of-ownership, full EN/FR i18n, and navigation link.

## Accomplishments

- **TypeScript types** added to `types.ts`: `FamilyHomeMetrics`, `HouseWithScore`, and `FamilyBatchResponse` interfaces matching backend models
- **API client** (`housesApi`) added to `api.ts` with three methods:
  - `scoreHouse()` — POST /api/analysis/family-score for single listing
  - `scoreBatch()` — POST /api/analysis/family-score-batch for multiple listings
  - `search()` — Two-step flow: GET /api/analysis/top-opportunities?property_types=HOUSE then POST family-score-batch
- **Houses page** (`/houses`) created with:
  - Region, price range, and min bedrooms filters
  - Card grid layout (not table) with photo, address, price, family score badge, key stats, pillar mini-bars, monthly cost
  - Client-side sort by Family Score (default), Price asc/desc, Bedrooms, Lot Size
  - Map view toggle reusing existing `PropertyMap` component (adapted data format)
  - Color-coded score badges (green >= 70, yellow >= 50, red < 50)
- **HouseDetail component** (slide-over sheet) with:
  - Photo gallery with carousel navigation
  - Price and large family score badge
  - 3-column score breakdown grid with circular progress visualizations for Livability/40, Value/35, Space/25
  - Detailed sub-score rows for each pillar
  - Cost of Ownership card (monthly mortgage, taxes, energy, insurance, total, welcome tax, total cash needed)
  - Property Details card with bedrooms, bathrooms, sqft, lot, year built, assessment, walk/transit/bike scores, condition
  - Risk flags section (flood zone, contaminated site warnings)
  - "View on Centris" action button
- **Navigation** updated: "Houses" / "Maisons" link added to Header (with Home icon), between Search and Compare
- **i18n**: 42 new keys added to both en.json and fr.json under `houses.*` and `header.houses` namespaces

## Files Created

- `frontend/src/app/houses/page.tsx` — Houses search page with card grid and filters
- `frontend/src/components/HouseDetail.tsx` — Slide-over detail component with score breakdown

## Files Modified

- `frontend/src/lib/types.ts` — Added FamilyHomeMetrics, HouseWithScore, FamilyBatchResponse types
- `frontend/src/lib/api.ts` — Added housesApi object with scoreHouse, scoreBatch, search functions
- `frontend/src/components/Header.tsx` — Added Houses navigation link with Home icon
- `frontend/src/i18n/en.json` — Added 42 houses.* keys + header.houses
- `frontend/src/i18n/fr.json` — Added 42 houses.* keys + header.houses (French translations)

## Decisions Made

1. **Card grid over table**: Houses are visual products for families; card layout with photos is more appropriate than the investment property table
2. **Two-step search flow**: Uses existing top-opportunities endpoint for listing retrieval, then family-score-batch for scoring (avoids new backend endpoint)
3. **Client-side filtering**: Min bedrooms and lot size filters are applied client-side after API results since the batch is already loaded
4. **PropertyMap adapter**: Created a lightweight adapter to convert HouseWithScore[] to PropertyWithMetrics[] for map reuse, mapping family_score to the metrics.score field
5. **Sheet component pattern**: Reused the same Sheet slide-over pattern as PropertyDetail for consistency
6. **Circular progress**: Used SVG-based circular progress for pillar scores instead of simple progress bars for visual distinction from investment scores

## Verification Results

- `npx tsc --noEmit` — Passes with zero errors
- `en.json` — Valid JSON, all houses.* keys present
- `fr.json` — Valid JSON, all houses.* keys present
- `/houses` route — File exists at `frontend/src/app/houses/page.tsx`

## Issues Encountered

None. All four tasks completed without blockers.

## Next Step

09-03: Quebec Geo Data Enrichment — School proximity (WFS), flood zones (CEHQ), parks (Montreal open data), scraper integration
