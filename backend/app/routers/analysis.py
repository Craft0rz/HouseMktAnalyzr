"""Investment analysis API endpoints."""

import logging
import os
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from housemktanalyzr.analysis.calculator import InvestmentCalculator
from housemktanalyzr.analysis.ranker import PropertyRanker
from housemktanalyzr.models.property import InvestmentMetrics, PropertyListing

router = APIRouter()
logger = logging.getLogger(__name__)

# Shared calculator and ranker instances
calculator = InvestmentCalculator()
ranker = PropertyRanker()


def _to_float(val) -> float | None:
    """Convert Decimal or other numeric types to float."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


async def _apply_location_score(
    metrics: InvestmentMetrics,
    city: str,
    condition_score: float | None = None,
) -> InvestmentMetrics:
    """Apply Location & Quality score (0-30) to the financial base (0-70).

    Fetches safety, vacancy, rent CAGR, and affordability data from DB,
    combines with AI condition score, and adds to the financial pillar.
    If DB data is unavailable, only condition score is applied.
    """
    safety_score = None
    vacancy_rate = None
    rent_cagr = None
    rent_to_income = None

    if os.environ.get("DATABASE_URL"):
        try:
            from ..db import (
                get_neighbourhood_stats_for_borough,
                get_demographics_for_city,
            )

            # Safety score from neighbourhood stats
            stats = await get_neighbourhood_stats_for_borough(city)
            if stats:
                safety_score = _to_float(stats.get("safety_score"))

            # Demographics for rent-to-income ratio
            demo = await get_demographics_for_city(city)
            if demo and demo.get("median_household_income"):
                income = _to_float(demo["median_household_income"])
                if income and income > 0 and metrics.estimated_monthly_rent > 0:
                    units = max(1, metrics.purchase_price // metrics.price_per_unit) if metrics.price_per_unit > 0 else 1
                    per_unit_rent = metrics.estimated_monthly_rent / units
                    rent_to_income = (per_unit_rent * 12) / income * 100

            # Rent trend data (vacancy + CAGR)
            try:
                from ..db import get_rent_history
                bedrooms = 2  # Default for zone-level comparison
                bed_map = {0: "bachelor", 1: "1br", 2: "2br", 3: "3br+"}
                bedroom_type = bed_map[bedrooms]
                history = await get_rent_history(city, bedroom_type, limit=10)
                if history:
                    vacancies = [r for r in history if r.get("vacancy_rate") is not None]
                    if vacancies:
                        vacancy_rate = _to_float(vacancies[0]["vacancy_rate"])

                    rents_with_years = [
                        (r["year"], float(r["avg_rent"]))
                        for r in history
                        if r.get("avg_rent") is not None
                    ]
                    if len(rents_with_years) >= 2:
                        rents_with_years.sort()
                        n = min(5, len(rents_with_years) - 1)
                        start_val = rents_with_years[-(n + 1)][1]
                        end_val = rents_with_years[-1][1]
                        if start_val > 0 and end_val > 0:
                            rent_cagr = ((end_val / start_val) ** (1 / n) - 1) * 100
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Location data fetch failed for {city}: {e}")

    location_score, location_breakdown = calculator.calculate_location_score(
        safety_score=safety_score,
        vacancy_rate=vacancy_rate,
        rent_cagr=rent_cagr,
        rent_to_income=rent_to_income,
        condition_score=condition_score,
    )

    if location_score > 0:
        metrics.score = min(100, round(metrics.score + location_score, 1))
        metrics.score_breakdown.update(
            {k: round(v, 1) for k, v in location_breakdown.items()}
        )

    return metrics


class AnalyzeRequest(BaseModel):
    """Request body for single property analysis."""

    listing: PropertyListing
    down_payment_pct: float = Field(default=0.20, ge=0.05, le=1.0)
    interest_rate: float = Field(default=0.05, ge=0.01, le=0.15)
    expense_ratio: float = Field(default=0.35, ge=0.10, le=0.60)


class AnalyzeBatchRequest(BaseModel):
    """Request body for batch property analysis."""

    listings: list[PropertyListing]
    down_payment_pct: float = Field(default=0.20, ge=0.05, le=1.0)
    interest_rate: float = Field(default=0.05, ge=0.01, le=0.15)
    expense_ratio: float = Field(default=0.35, ge=0.10, le=0.60)


class PropertyWithMetrics(BaseModel):
    """Property listing with its investment metrics."""

    listing: PropertyListing
    metrics: InvestmentMetrics


class BatchAnalysisResponse(BaseModel):
    """Response containing batch analysis results."""

    results: list[PropertyWithMetrics]
    count: int
    summary: dict


class QuickMetricsRequest(BaseModel):
    """Quick calculation without full property listing."""

    price: int = Field(ge=0, description="Purchase price in CAD")
    monthly_rent: int = Field(ge=0, description="Total monthly rent in CAD")
    units: int = Field(default=1, ge=1, description="Number of units")
    down_payment_pct: float = Field(default=0.20, ge=0.05, le=1.0)
    interest_rate: float = Field(default=0.05, ge=0.01, le=0.15)
    expense_ratio: float = Field(default=0.35, ge=0.10, le=0.60)


class QuickMetricsResponse(BaseModel):
    """Quick metrics response."""

    gross_yield: float
    cap_rate: float
    grm: float
    noi: int
    monthly_mortgage: int
    monthly_cash_flow: int
    annual_cash_flow: int
    cash_on_cash_return: float
    price_per_unit: int
    total_cash_needed: int


@router.post("/analyze", response_model=InvestmentMetrics)
async def analyze_property(request: AnalyzeRequest) -> InvestmentMetrics:
    """Analyze a single property listing.

    Calculates all investment metrics including cap rate, cash flow,
    gross yield, investment score, and neighbourhood quality bonus.
    """
    try:
        metrics = calculator.analyze_property(
            listing=request.listing,
            down_payment_pct=request.down_payment_pct,
            interest_rate=request.interest_rate,
            expense_ratio=request.expense_ratio,
        )
        metrics = await _apply_location_score(
            metrics, request.listing.city, request.listing.condition_score
        )
        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-batch", response_model=BatchAnalysisResponse)
async def analyze_batch(request: AnalyzeBatchRequest) -> BatchAnalysisResponse:
    """Analyze multiple properties and return ranked results.

    Returns properties sorted by investment score along with summary statistics.
    """
    try:
        results = ranker.analyze_batch(
            listings=request.listings,
            down_payment_pct=request.down_payment_pct,
            interest_rate=request.interest_rate,
            expense_ratio=request.expense_ratio,
        )

        # Apply location score and build response
        response_results = []
        for listing, metrics in results:
            metrics = await _apply_location_score(
                metrics, listing.city, listing.condition_score
            )
            response_results.append(PropertyWithMetrics(listing=listing, metrics=metrics))

        # Calculate summary statistics
        scores = [m.score for _, m in results]
        cap_rates = [m.cap_rate for _, m in results if m.cap_rate]
        cash_flows = [m.cash_flow_monthly for _, m in results if m.cash_flow_monthly is not None]

        summary = {
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "avg_cap_rate": round(sum(cap_rates) / len(cap_rates), 2) if cap_rates else 0,
            "avg_cash_flow": round(sum(cash_flows) / len(cash_flows), 0) if cash_flows else 0,
            "positive_cash_flow_count": len([cf for cf in cash_flows if cf > 0]),
            "total_analyzed": len(results),
        }

        return BatchAnalysisResponse(
            results=response_results,
            count=len(results),
            summary=summary,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")


@router.post("/quick-calc", response_model=QuickMetricsResponse)
async def quick_calculate(request: QuickMetricsRequest) -> QuickMetricsResponse:
    """Quick investment metrics calculation.

    Calculate investment metrics without needing a full property listing.
    Useful for quick "what-if" scenarios.
    """
    try:
        annual_rent = request.monthly_rent * 12

        # Core metrics
        gross_yield = calculator.gross_rental_yield(request.price, annual_rent)
        noi = calculator.estimate_noi(annual_rent, request.expense_ratio)
        cap_rate = calculator.cap_rate(request.price, noi)
        grm = calculator.gross_rent_multiplier(request.price, annual_rent)

        # Mortgage and cash flow
        down_payment = calculator.calculate_down_payment(request.price, request.down_payment_pct)
        principal = request.price - down_payment
        monthly_mortgage = calculator.calculate_mortgage_payment(principal, request.interest_rate)

        monthly_cash_flow = calculator.estimate_monthly_cash_flow(
            request.monthly_rent,
            monthly_mortgage,
            expense_ratio=request.expense_ratio,
        )

        # Cash-on-cash
        total_cash = calculator.calculate_total_cash_needed(request.price, request.down_payment_pct)
        annual_cash_flow = monthly_cash_flow * 12
        coc_return = calculator.cash_on_cash_return(annual_cash_flow, total_cash)

        return QuickMetricsResponse(
            gross_yield=round(gross_yield, 2),
            cap_rate=round(cap_rate, 2),
            grm=round(grm, 2),
            noi=noi,
            monthly_mortgage=monthly_mortgage,
            monthly_cash_flow=monthly_cash_flow,
            annual_cash_flow=annual_cash_flow,
            cash_on_cash_return=round(coc_return, 2),
            price_per_unit=request.price // request.units,
            total_cash_needed=total_cash,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation failed: {str(e)}")


@router.get("/mortgage")
async def calculate_mortgage(
    price: int = Query(ge=0, description="Purchase price"),
    down_payment_pct: float = Query(default=0.20, ge=0.05, le=1.0),
    interest_rate: float = Query(default=0.05, ge=0.01, le=0.15),
    amortization_years: int = Query(default=30, ge=5, le=30),
) -> dict:
    """Calculate mortgage payment details.

    Uses Canadian mortgage formula with semi-annual compounding.
    """
    down_payment = calculator.calculate_down_payment(price, down_payment_pct)
    principal = price - down_payment
    monthly_payment = calculator.calculate_mortgage_payment(
        principal, interest_rate, amortization_years
    )
    total_cash = calculator.calculate_total_cash_needed(price, down_payment_pct)

    return {
        "price": price,
        "down_payment": down_payment,
        "down_payment_pct": down_payment_pct,
        "principal": principal,
        "interest_rate": interest_rate,
        "amortization_years": amortization_years,
        "monthly_payment": monthly_payment,
        "total_cash_needed": total_cash,
    }


@router.get("/top-opportunities")
async def get_top_opportunities(
    region: str = Query(default="montreal"),
    property_types: Optional[str] = Query(default="DUPLEX,TRIPLEX,QUADPLEX"),
    min_price: Optional[int] = Query(default=None),
    max_price: Optional[int] = Query(default=None),
    min_score: float = Query(default=50.0, ge=0, le=100),
    limit: int = Query(default=10, ge=1, le=50),
) -> BatchAnalysisResponse:
    """Find top investment opportunities.

    Uses cached listings when available, otherwise scrapes and caches.
    Analysis scoring always runs fresh on the listings.
    """
    from housemktanalyzr.collectors.centris import CentrisScraper

    types_list = None
    if property_types:
        types_list = [t.strip().upper() for t in property_types.split(",")]

    listings = []

    # DB-first: query Postgres for cached listings
    if os.environ.get("DATABASE_URL"):
        try:
            from ..db import get_cached_listings
            cached = await get_cached_listings(
                property_types=types_list, min_price=min_price,
                max_price=max_price, region=region, limit=200,
            )
            if cached:
                listings = [PropertyListing(**d) for d in cached]
                logger.info(f"Top-opportunities DB hit: {len(listings)} listings")
        except Exception as e:
            logger.warning(f"DB read failed: {e}")

    # Fallback: scrape only if DB is empty
    if not listings:
        try:
            async with CentrisScraper() as scraper:
                listings = await scraper.fetch_listings_multi_type(
                    region=region, property_types=types_list,
                    min_price=min_price, max_price=max_price, enrich=True,
                )

            if os.environ.get("DATABASE_URL") and listings:
                try:
                    from ..db import cache_listings
                    await cache_listings(listings, region=region)
                except Exception as e:
                    logger.warning(f"Cache write failed: {e}")

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    if not listings:
        return BatchAnalysisResponse(results=[], count=0, summary={})

    # Analyze all listings (always fresh)
    results = ranker.analyze_batch(listings)

    # Apply location score to each result
    enriched = []
    for listing, metrics in results:
        metrics = await _apply_location_score(
            metrics, listing.city, listing.condition_score
        )
        enriched.append((listing, metrics))
    results = enriched

    # Re-sort by score (location may change ordering)
    results.sort(key=lambda x: x[1].score, reverse=True)

    # Filter by minimum score
    filtered = [(l, m) for l, m in results if m.score >= min_score]

    # Get top N by score
    top_results = filtered[:limit]

    response_results = [
        PropertyWithMetrics(listing=l, metrics=m) for l, m in top_results
    ]

    summary = {
        "total_found": len(listings),
        "passed_score_filter": len(filtered),
        "returned": len(top_results),
        "min_score_threshold": min_score,
    }

    return BatchAnalysisResponse(
        results=response_results, count=len(top_results), summary=summary,
    )
