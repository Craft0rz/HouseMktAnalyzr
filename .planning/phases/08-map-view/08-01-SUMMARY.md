---
phase: 08-map-view
plan: 01
status: complete
---

# 08-01 Summary: Interactive Map View

**One-liner**: Added an interactive Leaflet map view to the search page with score-colored property markers and a Table/Map toggle.

## Accomplishments

- Installed `leaflet`, `react-leaflet`, and `@types/leaflet`; imported Leaflet CSS globally in layout.tsx
- Created `PropertyMap` component with OpenStreetMap tiles, score-colored circle markers (green/yellow/red), and info popups showing address, price, score, cap rate, and property type
- Auto-fits map bounds to visible markers; defaults to Montreal center when no data
- Skips properties without geocoded lat/lng; shows a "no geocoded listings" message when no properties have coordinates
- Added Table/Map toggle buttons (List and Map icons from lucide-react) to the search results header, adjacent to status filters
- Map view loads via `next/dynamic` with `{ ssr: false }` to prevent Leaflet SSR crashes
- Clicking "View Details" in a marker popup opens the existing PropertyDetail sheet
- Added 4 new i18n keys in both English and French (tableView, mapView, viewDetails, noGeocodedListings)

## Files Created

- `frontend/src/components/PropertyMap.tsx` -- New map component with Leaflet markers and popups

## Files Modified

- `frontend/src/app/layout.tsx` -- Added `import 'leaflet/dist/leaflet.css'`
- `frontend/src/app/search/page.tsx` -- Added viewMode state, dynamic PropertyMap import, toggle buttons, conditional rendering
- `frontend/src/i18n/en.json` -- Added 4 search.* i18n keys
- `frontend/src/i18n/fr.json` -- Added 4 search.* i18n keys
- `frontend/package.json` -- Added leaflet, react-leaflet, @types/leaflet dependencies

## Decisions Made

- Used `divIcon` with inline HTML for markers instead of default Leaflet icon (avoids broken image issue with bundlers)
- Used OpenStreetMap tiles (free, no API key required)
- Used `next/dynamic` with `{ ssr: false }` for PropertyMap to avoid Leaflet window dependency during SSR
- Marker colors: green (#22c55e) for score >= 70, yellow (#eab308) for 50-69, red (#ef4444) for < 50
- Map container fixed at `h-[600px]` with rounded border to match app design
- Toggle buttons placed to the right of status filters with a border separator

## Issues Encountered

- None. All 3 tasks completed without errors. TypeScript and Next.js build pass cleanly.

## Next Step

- Phase 08-01 is complete. Continue with remaining v3.0 roadmap items (custom domain, Walk Score in list view, filtering by Walk Score, etc.)
