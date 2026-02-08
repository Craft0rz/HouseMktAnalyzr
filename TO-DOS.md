# TO-DOS

## Compare Tab — Add New Market Data - 2026-02-07 21:30

- **Add comparable market data to Compare tab** - Incorporate all newly added data sources (rent trends, demographics, safety, market rates) into the property comparison view. **Problem:** Compare tab currently only shows basic financial metrics; the 4 phases of market intelligence data aren't surfaced there, making side-by-side comparison incomplete. **Files:** `frontend/src/app/compare/page.tsx`, `frontend/src/lib/types.ts`, `backend/app/routers/analysis.py`.

## Favorites / Watch List - 2026-02-07 21:31

- **Add favorites/watch list feature** - Allow users to save properties to a persistent watch list for monitoring. **Problem:** No way to bookmark or track interesting properties across sessions; users lose track of properties they want to revisit. **Files:** `frontend/src/app/portfolio/page.tsx` (or new route), `backend/app/routers/` (new endpoint), `backend/app/db.py` (new table). **Solution:** Local storage for MVP, then DB-backed if user accounts are added later.

