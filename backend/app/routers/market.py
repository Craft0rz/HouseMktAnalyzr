"""Market intelligence API endpoints.

Serves macro-economic data (interest rates, CPI, unemployment)
and rental market intelligence from CMHC.
"""

import logging
import os
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


def _has_db() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


class MarketObservation(BaseModel):
    date: str
    value: float


class RateSeriesResponse(BaseModel):
    series_id: str
    label: str
    latest_value: float | None
    latest_date: str | None
    direction: str  # "up", "down", "stable"
    observations: list[MarketObservation]


class MarketRatesResponse(BaseModel):
    mortgage_5yr: RateSeriesResponse | None
    policy_rate: RateSeriesResponse | None
    prime_rate: RateSeriesResponse | None
    cpi: RateSeriesResponse | None
    last_updated: str | None


class MarketSummaryResponse(BaseModel):
    mortgage_rate: float | None
    policy_rate: float | None
    prime_rate: float | None
    cpi: float | None
    mortgage_direction: str
    policy_direction: str


def _rate_history_to_response(history) -> RateSeriesResponse:
    """Convert a RateHistory dataclass to API response."""
    latest = history.latest
    return RateSeriesResponse(
        series_id=history.series_id,
        label=history.label,
        latest_value=latest.value if latest else None,
        latest_date=latest.date.isoformat() if latest else None,
        direction=history.direction,
        observations=[
            MarketObservation(date=obs.date.isoformat(), value=obs.value)
            for obs in history.observations
        ],
    )


@router.get("/rates", response_model=MarketRatesResponse)
async def get_market_rates(
    lookback_months: int = Query(default=12, ge=1, le=60, description="Months of history"),
):
    """Get current interest rates and trends from Bank of Canada.

    Returns mortgage rates, policy rate, prime rate, and CPI with history.
    Data is cached in DB and refreshed daily by the background worker.
    Falls back to live API if DB has no data.
    """
    from housemktanalyzr.enrichment.market_data import BankOfCanadaClient

    # Try DB first
    if _has_db():
        try:
            from ..db import get_market_series, get_latest_market_value

            start_date = date.today() - timedelta(days=lookback_months * 30)
            result = {}

            for name, series_key in [
                ("mortgage_5yr", "boc_mortgage_5yr"),
                ("policy_rate", "boc_policy_rate"),
                ("prime_rate", "boc_prime_rate"),
                ("cpi", "boc_cpi"),
            ]:
                latest = await get_latest_market_value(series_key)
                observations = await get_market_series(
                    series_key, start_date=start_date
                )

                if latest and observations:
                    # Calculate direction from last two observations
                    obs_sorted = sorted(observations, key=lambda x: x["date"])
                    direction = "stable"
                    if len(obs_sorted) >= 2:
                        diff = obs_sorted[-1]["value"] - obs_sorted[-2]["value"]
                        if abs(diff) >= 0.001:
                            direction = "up" if diff > 0 else "down"

                    result[name] = RateSeriesResponse(
                        series_id=series_key,
                        label=name.replace("_", " ").title(),
                        latest_value=latest["value"],
                        latest_date=latest["date"],
                        direction=direction,
                        observations=[
                            MarketObservation(date=o["date"], value=o["value"])
                            for o in obs_sorted
                        ],
                    )

            if result:
                last_updated = None
                for v in result.values():
                    if v and v.latest_date:
                        last_updated = v.latest_date
                        break
                return MarketRatesResponse(
                    mortgage_5yr=result.get("mortgage_5yr"),
                    policy_rate=result.get("policy_rate"),
                    prime_rate=result.get("prime_rate"),
                    cpi=result.get("cpi"),
                    last_updated=last_updated,
                )
        except Exception as e:
            logger.warning(f"DB read for market data failed, falling back to live API: {e}")

    # Fallback: fetch live from BoC
    client = BankOfCanadaClient()
    try:
        lookback_years = max(1, lookback_months // 12)
        rates = await client.get_all_rates(lookback_years=lookback_years)

        result = {}
        for name in ["mortgage_5yr", "policy_rate", "prime_rate", "cpi"]:
            if name in rates:
                result[name] = _rate_history_to_response(rates[name])

        last_updated = None
        for v in result.values():
            if v and v.latest_date:
                last_updated = v.latest_date
                break

        return MarketRatesResponse(
            mortgage_5yr=result.get("mortgage_5yr"),
            policy_rate=result.get("policy_rate"),
            prime_rate=result.get("prime_rate"),
            cpi=result.get("cpi"),
            last_updated=last_updated,
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch market rates: {str(e)}",
        )
    finally:
        await client.close()


@router.get("/summary", response_model=MarketSummaryResponse)
async def get_market_summary():
    """Get a compact summary of current market rates.

    Returns just the latest values and trend directions,
    ideal for dashboard widgets and property detail cards.
    """
    from housemktanalyzr.enrichment.market_data import BankOfCanadaClient

    # Try DB first
    if _has_db():
        try:
            from ..db import get_market_series

            values = {}
            directions = {}
            for name, series_key in [
                ("mortgage_rate", "boc_mortgage_5yr"),
                ("policy_rate", "boc_policy_rate"),
                ("prime_rate", "boc_prime_rate"),
                ("cpi", "boc_cpi"),
            ]:
                obs = await get_market_series(series_key, limit=2)
                if obs:
                    values[name] = obs[0]["value"]  # most recent (DESC order)
                    if len(obs) >= 2:
                        diff = obs[0]["value"] - obs[1]["value"]
                        directions[name] = "up" if diff > 0.001 else ("down" if diff < -0.001 else "stable")
                    else:
                        directions[name] = "stable"

            if values:
                return MarketSummaryResponse(
                    mortgage_rate=values.get("mortgage_rate"),
                    policy_rate=values.get("policy_rate"),
                    prime_rate=values.get("prime_rate"),
                    cpi=values.get("cpi"),
                    mortgage_direction=directions.get("mortgage_rate", "stable"),
                    policy_direction=directions.get("policy_rate", "stable"),
                )
        except Exception as e:
            logger.warning(f"DB market summary failed: {e}")

    # Fallback: live fetch
    client = BankOfCanadaClient()
    try:
        rates = await client.get_all_rates(lookback_years=1)

        mortgage = rates.get("mortgage_5yr")
        policy = rates.get("policy_rate")
        prime = rates.get("prime_rate")
        cpi = rates.get("cpi")

        return MarketSummaryResponse(
            mortgage_rate=mortgage.latest.value if mortgage and mortgage.latest else None,
            policy_rate=policy.latest.value if policy and policy.latest else None,
            prime_rate=prime.latest.value if prime and prime.latest else None,
            cpi=cpi.latest.value if cpi and cpi.latest else None,
            mortgage_direction=mortgage.direction if mortgage else "stable",
            policy_direction=policy.direction if policy else "stable",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch market summary: {str(e)}",
        )
    finally:
        await client.close()


# --- Rental Market Intelligence ---


class RentForecastResponse(BaseModel):
    year: int
    projected_rent: float
    lower_bound: float
    upper_bound: float


class RentTrendResponse(BaseModel):
    zone: str
    bedroom_type: str
    current_rent: float | None
    years: list[int]
    rents: list[float]
    annual_growth_rate: float | None
    growth_direction: str
    forecasts: list[RentForecastResponse]
    vacancy_rate: float | None
    vacancy_direction: str


class RentZonesResponse(BaseModel):
    zones: list[str]


@router.get("/rents/zones", response_model=RentZonesResponse)
async def get_rent_zones():
    """Get list of available CMHC zones with rent data."""
    if _has_db():
        try:
            from ..db import get_rent_zones as db_get_zones
            zones = await db_get_zones()
            if zones:
                return RentZonesResponse(zones=zones)
        except Exception as e:
            logger.warning(f"DB rent zones lookup failed: {e}")

    # Fallback: fetch live from CMHC
    from housemktanalyzr.enrichment.cmhc_client import CMHCClient
    client = CMHCClient()
    try:
        rents = await client.get_rents_by_zone()
        zones = sorted(set(r.zone for r in rents))
        return RentZonesResponse(zones=zones)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch CMHC zones: {e}")
    finally:
        await client.close()


@router.get("/rents", response_model=RentTrendResponse)
async def get_rent_trend(
    zone: str = Query(description="CMHC zone name"),
    bedrooms: int = Query(default=2, ge=0, le=3, description="Bedroom count (0=bachelor, 1-3)"),
):
    """Get rent trend and forecast for a specific zone and bedroom type.

    Returns historical rents, growth rate, trend direction, and 3-year forecast.
    Data is cached in DB and refreshed annually by the background worker.
    Falls back to live CMHC API if DB has no data.
    """
    from housemktanalyzr.enrichment.rent_intel import analyze_zone_rent

    bed_map = {0: "bachelor", 1: "1br", 2: "2br", 3: "3br+"}
    bedroom_type = bed_map[bedrooms]

    # Try DB first
    if _has_db():
        try:
            from ..db import get_rent_history

            history = await get_rent_history(zone, bedroom_type, limit=20)
            if history:
                hist_data = [
                    {"year": r["year"], "rent": float(r["avg_rent"])}
                    for r in history
                    if r.get("avg_rent") is not None
                ]
                vacancies = [r for r in history if r.get("vacancy_rate") is not None]
                current_vac = float(vacancies[0]["vacancy_rate"]) if vacancies else None
                prev_vac = float(vacancies[1]["vacancy_rate"]) if len(vacancies) >= 2 else None

                trend = analyze_zone_rent(
                    zone, bedroom_type, hist_data,
                    current_vacancy=current_vac,
                    previous_vacancy=prev_vac,
                )
                return RentTrendResponse(
                    zone=trend.zone,
                    bedroom_type=trend.bedroom_type,
                    current_rent=trend.current_rent,
                    years=trend.years,
                    rents=trend.rents,
                    annual_growth_rate=trend.annual_growth_rate,
                    growth_direction=trend.growth_direction,
                    forecasts=[
                        RentForecastResponse(
                            year=f.year,
                            projected_rent=f.projected_rent,
                            lower_bound=f.lower_bound,
                            upper_bound=f.upper_bound,
                        )
                        for f in trend.forecasts
                    ],
                    vacancy_rate=trend.vacancy_rate,
                    vacancy_direction=trend.vacancy_direction,
                )
        except Exception as e:
            logger.warning(f"DB rent lookup failed: {e}")

    # Fallback: fetch live from CMHC
    from housemktanalyzr.enrichment.cmhc_client import CMHCClient
    client = CMHCClient()
    try:
        historical = await client.get_historical_rents()

        bed_attr_map = {0: "bachelor", 1: "one_br", 2: "two_br", 3: "three_br_plus"}
        attr = bed_attr_map[bedrooms]
        hist_data = [
            {"year": r.year, "rent": getattr(r, attr)}
            for r in historical
            if getattr(r, attr) is not None
        ]

        trend = analyze_zone_rent(zone, bedroom_type, hist_data)
        return RentTrendResponse(
            zone=trend.zone,
            bedroom_type=trend.bedroom_type,
            current_rent=trend.current_rent,
            years=trend.years,
            rents=trend.rents,
            annual_growth_rate=trend.annual_growth_rate,
            growth_direction=trend.growth_direction,
            forecasts=[
                RentForecastResponse(
                    year=f.year,
                    projected_rent=f.projected_rent,
                    lower_bound=f.lower_bound,
                    upper_bound=f.upper_bound,
                )
                for f in trend.forecasts
            ],
            vacancy_rate=trend.vacancy_rate,
            vacancy_direction=trend.vacancy_direction,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch CMHC rent data: {e}")
    finally:
        await client.close()
