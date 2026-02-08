# TO-DOS

## Compare Tab — Add New Market Data - 2026-02-07 21:30

- **Add comparable market data to Compare tab** - Incorporate all newly added data sources (rent trends, demographics, safety, market rates) into the property comparison view. **Problem:** Compare tab currently only shows basic financial metrics; the 4 phases of market intelligence data aren't surfaced there, making side-by-side comparison incomplete. **Files:** `frontend/src/app/compare/page.tsx`, `frontend/src/lib/types.ts`, `backend/app/routers/analysis.py`.

## Favorites / Watch List - 2026-02-07 21:31

- **Add favorites/watch list feature** - Allow users to save properties to a persistent watch list for monitoring. **Problem:** No way to bookmark or track interesting properties across sessions; users lose track of properties they want to revisit. **Files:** `frontend/src/app/portfolio/page.tsx` (or new route), `backend/app/routers/` (new endpoint), `backend/app/db.py` (new table). **Solution:** Local storage for MVP, then DB-backed if user accounts are added later.


## Login System / User Tracking - 2026-02-07 23:15

- **Build user authentication system** - Add login/signup so usage can be tracked per user. **Problem:** No way to identify who is using the tool; needed for usage analytics, personalized features (saved searches, watch lists), and potential access control. **Files:** `backend/app/main.py` (add auth middleware), `backend/app/routers/` (new `auth.py` router), `backend/app/db.py` (new `users` table), `frontend/src/lib/providers.tsx` (auth context), `frontend/src/components/Header.tsx` (login/logout UI). **Solution:** Start with email+password or OAuth (Google) via FastAPI + JWT tokens; store sessions server-side; add auth context in frontend; protect API routes with dependency injection. Consider NextAuth.js for frontend or a simple custom JWT flow.


## Scrape Status Dashboard - 2026-02-08 00:15

- **Build scrape status dashboard with live tracking** - Add a dashboard page showing scraping activity details, status of each scrape job, and live progress tracking. **Problem:** No visibility into scraping operations; users can't see what data is being collected, when it was last updated, or if scrapes are failing. **Files:** `frontend/src/app/` (new route), `backend/app/routers/` (new status endpoint), `backend/app/db.py` (scrape job tracking table). **Solution:** Backend tracks scrape jobs (start time, status, items found, errors); frontend displays a dashboard with job history, current activity, and live progress indicators via polling or SSE.
