# TO-DOS

## Compare Tab — Add New Market Data - 2026-02-07 21:30

- **Add comparable market data to Compare tab** - Incorporate all newly added data sources (rent trends, demographics, safety, market rates) into the property comparison view. **Problem:** Compare tab currently only shows basic financial metrics; the 4 phases of market intelligence data aren't surfaced there, making side-by-side comparison incomplete. **Files:** `frontend/src/app/compare/page.tsx`, `frontend/src/lib/types.ts`, `backend/app/routers/analysis.py`.

## Favorites / Watch List - 2026-02-07 21:31

- **Add favorites/watch list feature** - Allow users to save properties to a persistent watch list for monitoring. **Problem:** No way to bookmark or track interesting properties across sessions; users lose track of properties they want to revisit. **Files:** `frontend/src/app/portfolio/page.tsx` (or new route), `backend/app/routers/` (new endpoint), `backend/app/db.py` (new table). **Solution:** Local storage for MVP, then DB-backed if user accounts are added later.

## Update UI Score Breakdown - 2026-02-07 21:45

- **Update PropertyDetail score display for two-pillar breakdown** - Show the Financial (0-70) and Location & Quality (0-30) pillars separately in the UI instead of just a single total score. **Problem:** The backend now returns a two-pillar score (Financial 70 + Location 30 = 100) with detailed breakdown keys (cap_rate, cash_flow, price_per_unit for financial; safety, vacancy, rent_growth, affordability, condition for location), but the frontend only displays a single aggregate score number. Users can't see what's driving their score. **Files:** `frontend/src/components/PropertyDetail.tsx`, `frontend/src/components/PropertyTable.tsx`, `frontend/src/lib/types.ts` (InvestmentMetrics.score_breakdown), `src/housemktanalyzr/analysis/calculator.py:calculate_location_score`. **Solution:** Add a score breakdown card/section in PropertyDetail showing each pillar with its sub-components as progress bars or a radar chart. Update PropertyTable tooltip to preview the breakdown.

## Login System / User Tracking - 2026-02-07 23:15

- **Build user authentication system** - Add login/signup so usage can be tracked per user. **Problem:** No way to identify who is using the tool; needed for usage analytics, personalized features (saved searches, watch lists), and potential access control. **Files:** `backend/app/main.py` (add auth middleware), `backend/app/routers/` (new `auth.py` router), `backend/app/db.py` (new `users` table), `frontend/src/lib/providers.tsx` (auth context), `frontend/src/components/Header.tsx` (login/logout UI). **Solution:** Start with email+password or OAuth (Google) via FastAPI + JWT tokens; store sessions server-side; add auth context in frontend; protect API routes with dependency injection. Consider NextAuth.js for frontend or a simple custom JWT flow.


