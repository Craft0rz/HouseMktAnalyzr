# TO-DOS

## Login System / User Tracking - 2026-02-07 23:15

- **Build user authentication system** - Add login/signup so usage can be tracked per user. **Problem:** No way to identify who is using the tool; needed for usage analytics, personalized features (saved searches, watch lists), and potential access control. **Files:** `backend/app/main.py` (add auth middleware), `backend/app/routers/` (new `auth.py` router), `backend/app/db.py` (new `users` table), `frontend/src/lib/providers.tsx` (auth context), `frontend/src/components/Header.tsx` (login/logout UI). **Solution:** Start with email+password or OAuth (Google) via FastAPI + JWT tokens; store sessions server-side; add auth context in frontend; protect API routes with dependency injection. Consider NextAuth.js for frontend or a simple custom JWT flow.

