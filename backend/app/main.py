"""FastAPI application for HouseMktAnalyzr API."""

import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .auth import SECRET_KEY as _JWT_SECRET, ALGORITHM as _JWT_ALGO
from .db import init_pool, close_pool, get_pool
from .routers import admin, alerts, analysis, auth, market, portfolio, properties, scraper
from .scraper_worker import ScraperWorker

logger = logging.getLogger(__name__)


class UsageTrackingMiddleware(BaseHTTPMiddleware):
    """Log every API request to the usage_logs table."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Extract user_id from Bearer token (best-effort, never block)
        user_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth_header[7:], _JWT_SECRET, algorithms=[_JWT_ALGO]
                )
                user_id = uuid.UUID(payload["sub"])
            except Exception:
                pass

        # Fire-and-forget insert (don't slow down the response)
        try:
            pool = get_pool()
            await pool.execute(
                """INSERT INTO usage_logs (user_id, endpoint, method, status_code, response_time_ms)
                   VALUES ($1, $2, $3, $4, $5)""",
                user_id,
                request.url.path,
                request.method,
                response.status_code,
                elapsed_ms,
            )
        except Exception:
            pass  # never break requests for logging

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown: DB pool + scraper worker lifecycle."""
    if os.environ.get("DATABASE_URL"):
        pool = await init_pool()
        logger.info("Database connected")

        worker = ScraperWorker(pool=pool)
        app.state.scraper_worker = worker
        await worker.start()
        logger.info("Background scraper worker started")
    else:
        logger.warning("DATABASE_URL not set — running without database")
        app.state.scraper_worker = None

    yield

    if app.state.scraper_worker:
        await app.state.scraper_worker.stop()
    await close_pool()


app = FastAPI(
    title="HouseMktAnalyzr API",
    description="Real estate investment analysis API for Quebec",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS for frontend
allowed_origins = [
    "http://localhost:3000",  # Next.js dev
    "http://127.0.0.1:3000",
]
# Add production frontend URL from env var
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if os.environ.get("FRONTEND_URL", "").startswith("https"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(UsageTrackingMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])
app.include_router(scraper.router, prefix="/api/scraper", tags=["Scraper"])
app.include_router(market.router, prefix="/api/market", tags=["Market"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "HouseMktAnalyzr API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    result = {"status": "healthy"}
    if os.environ.get("DATABASE_URL"):
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            result["database"] = "connected"
        except Exception:
            result["database"] = "disconnected"
    return result
