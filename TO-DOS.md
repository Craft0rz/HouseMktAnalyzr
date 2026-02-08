# TO-DOS

## Login System / User Tracking - 2026-02-07 23:15

- **Build user authentication system** - Add login/signup so usage can be tracked per user. **Problem:** No way to identify who is using the tool; needed for usage analytics, personalized features (saved searches, watch lists), and potential access control. **Files:** `backend/app/main.py` (add auth middleware), `backend/app/routers/` (new `auth.py` router), `backend/app/db.py` (new `users` table), `frontend/src/lib/providers.tsx` (auth context), `frontend/src/components/Header.tsx` (login/logout UI). **Solution:** Start with email+password or OAuth (Google) via FastAPI + JWT tokens; store sessions server-side; add auth context in frontend; protect API routes with dependency injection. Consider NextAuth.js for frontend or a simple custom JWT flow.


## Hide Empty Price History Graph - 2026-02-08 08:39

- **Hide price history graph when no price changes exist** - Don't render the price history chart when there are no actual price changes to display. **Problem:** The price history section currently shows even when there are zero price changes, displaying an empty or pointless graph. Only the "days on market" stat may be present, which doesn't need a chart. **Files:** `frontend/src/components/PropertyDetail.tsx:367-442` (price history Card and LineChart rendering). **Solution:** The outer conditional at line 367 already checks `priceHistory.changes.length > 0 || priceHistory.days_on_market != null`, but the entire Card (including the chart area) renders when only `days_on_market` is set. Either hide the whole section when `changes.length === 0`, or restructure so the chart portion is skipped and only days-on-market stats show when there are no changes.
