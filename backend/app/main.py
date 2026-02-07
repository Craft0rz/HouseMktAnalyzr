"""FastAPI application for HouseMktAnalyzr API."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_pool, close_pool, get_pool
from .routers import alerts, analysis, portfolio, properties

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown: DB pool lifecycle."""
    if os.environ.get("DATABASE_URL"):
        await init_pool()
        logger.info("Database connected")
    else:
        logger.warning("DATABASE_URL not set — running without database")
    yield
    await close_pool()


app = FastAPI(
    title="HouseMktAnalyzr API",
    description="Real estate investment analysis API for Greater Montreal",
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
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["Portfolio"])


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
