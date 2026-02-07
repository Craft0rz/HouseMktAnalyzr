"""FastAPI application for HouseMktAnalyzr API."""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import alerts, analysis, properties

app = FastAPI(
    title="HouseMktAnalyzr API",
    description="Real estate investment analysis API for Greater Montreal",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])


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
    return {"status": "healthy"}
