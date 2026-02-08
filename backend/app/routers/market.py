"""Market intelligence API endpoints.

Serves macro-economic data (interest rates, CPI, unemployment),
rental market intelligence from CMHC, and census demographics.
"""

import logging
import os
from datetime import date, timedelta
from decimal import Decimal

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
    cagr_5yr: float | None
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
                    cagr_5yr=trend.cagr_5yr,
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
            cagr_5yr=trend.cagr_5yr,
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


# --- Demographics ---


class DemographicProfileResponse(BaseModel):
    municipality: str
    csd_code: str
    population: int | None
    population_2016: int | None
    pop_change_pct: float | None
    avg_household_size: float | None
    total_households: int | None
    median_household_income: int | None
    median_after_tax_income: int | None
    avg_household_income: int | None
    rent_to_income_ratio: float | None


class DemographicsListResponse(BaseModel):
    profiles: list[DemographicProfileResponse]
    count: int


def _decimal_to_num(val):
    """Convert Decimal values to int/float for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        if val == int(val):
            return int(val)
        return float(val)
    return val


@router.get("/demographics", response_model=DemographicProfileResponse)
async def get_demographics(
    city: str = Query(description="City or municipality name"),
    monthly_rent: int | None = Query(default=None, description="Optional monthly rent for rent-to-income ratio"),
):
    """Get census demographics for a city/municipality.

    Returns population, income, household data from StatCan 2021 Census.
    Data is cached in DB and refreshed monthly by the background worker.
    Falls back to live StatCan API if DB has no data.
    """
    # Try DB first
    if _has_db():
        try:
            from ..db import get_demographics_for_city
            profile = await get_demographics_for_city(city)
            if profile:
                income = _decimal_to_num(profile.get("median_household_income"))
                ratio = None
                if income and monthly_rent:
                    ratio = round((monthly_rent * 12) / income * 100, 1)

                return DemographicProfileResponse(
                    municipality=profile["municipality"],
                    csd_code=profile["csd_code"],
                    population=_decimal_to_num(profile.get("population")),
                    population_2016=_decimal_to_num(profile.get("population_2016")),
                    pop_change_pct=_decimal_to_num(profile.get("pop_change_pct")),
                    avg_household_size=_decimal_to_num(profile.get("avg_household_size")),
                    total_households=_decimal_to_num(profile.get("total_households")),
                    median_household_income=income,
                    median_after_tax_income=_decimal_to_num(profile.get("median_after_tax_income")),
                    avg_household_income=_decimal_to_num(profile.get("avg_household_income")),
                    rent_to_income_ratio=ratio,
                )
        except Exception as e:
            logger.warning(f"DB demographics lookup failed: {e}")

    # Fallback: live StatCan API
    from housemktanalyzr.enrichment.demographics import StatCanCensusClient
    client = StatCanCensusClient()
    try:
        profile = await client.get_demographics_for_city(city)
        if not profile:
            raise HTTPException(status_code=404, detail=f"No demographics found for: {city}")

        ratio = None
        if profile.median_household_income and monthly_rent:
            ratio = round((monthly_rent * 12) / profile.median_household_income * 100, 1)

        return DemographicProfileResponse(
            municipality=profile.municipality,
            csd_code=profile.csd_code,
            population=profile.population,
            population_2016=profile.population_2016,
            pop_change_pct=profile.pop_change_pct,
            avg_household_size=profile.avg_household_size,
            total_households=profile.total_households,
            median_household_income=profile.median_household_income,
            median_after_tax_income=profile.median_after_tax_income,
            avg_household_income=profile.avg_household_income,
            rent_to_income_ratio=ratio,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch demographics: {e}")
    finally:
        await client.close()


@router.get("/demographics/all", response_model=DemographicsListResponse)
async def get_all_demographics():
    """Get all cached demographics profiles for Greater Montreal."""
    if _has_db():
        try:
            from ..db import get_all_demographics as db_get_all
            profiles = await db_get_all()
            if profiles:
                items = [
                    DemographicProfileResponse(
                        municipality=p["municipality"],
                        csd_code=p["csd_code"],
                        population=_decimal_to_num(p.get("population")),
                        population_2016=_decimal_to_num(p.get("population_2016")),
                        pop_change_pct=_decimal_to_num(p.get("pop_change_pct")),
                        avg_household_size=_decimal_to_num(p.get("avg_household_size")),
                        total_households=_decimal_to_num(p.get("total_households")),
                        median_household_income=_decimal_to_num(p.get("median_household_income")),
                        median_after_tax_income=_decimal_to_num(p.get("median_after_tax_income")),
                        avg_household_income=_decimal_to_num(p.get("avg_household_income")),
                        rent_to_income_ratio=None,
                    )
                    for p in profiles
                ]
                return DemographicsListResponse(profiles=items, count=len(items))
        except Exception as e:
            logger.warning(f"DB demographics list failed: {e}")

    # Fallback: fetch all from StatCan
    from housemktanalyzr.enrichment.demographics import StatCanCensusClient
    client = StatCanCensusClient()
    try:
        profiles = await client.get_demographics()
        items = [
            DemographicProfileResponse(
                municipality=p.municipality,
                csd_code=p.csd_code,
                population=p.population,
                population_2016=p.population_2016,
                pop_change_pct=p.pop_change_pct,
                avg_household_size=p.avg_household_size,
                total_households=p.total_households,
                median_household_income=p.median_household_income,
                median_after_tax_income=p.median_after_tax_income,
                avg_household_income=p.avg_household_income,
                rent_to_income_ratio=None,
            )
            for p in profiles
        ]
        return DemographicsListResponse(profiles=items, count=len(items))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch demographics: {e}")
    finally:
        await client.close()


# --- Neighbourhood Safety & Development ---


class CrimeStatsResponse(BaseModel):
    total_crimes: int
    violent_crimes: int
    property_crimes: int
    year_over_year_change_pct: float | None


class PermitStatsResponse(BaseModel):
    total_permits: int
    construction_permits: int
    transform_permits: int
    demolition_permits: int
    total_cost: float


class TaxRateResponse(BaseModel):
    residential_rate: float
    total_tax_rate: float
    annual_tax_estimate: float | None


class NeighbourhoodResponse(BaseModel):
    borough: str
    year: int
    crime: CrimeStatsResponse | None
    permits: PermitStatsResponse | None
    tax: TaxRateResponse | None
    safety_score: float | None
    gentrification_signal: str | None


@router.get("/neighbourhood", response_model=NeighbourhoodResponse)
async def get_neighbourhood(
    borough: str = Query(description="Borough or neighbourhood name"),
    assessment: int | None = Query(default=None, description="Property assessment for tax estimate"),
):
    """Get safety, permit activity, and tax data for a Montreal borough.

    Returns crime stats, building permits, tax rates, safety score,
    and gentrification signal from Montreal Open Data.
    """
    current_year = date.today().year - 1

    # Try DB first
    if _has_db():
        try:
            from ..db import get_neighbourhood_stats_for_borough
            stats = await get_neighbourhood_stats_for_borough(borough)
            if stats:
                tax_estimate = None
                res_rate = _decimal_to_num(stats.get("tax_rate_residential"))
                total_rate = _decimal_to_num(stats.get("tax_rate_total"))
                if total_rate and assessment:
                    tax_estimate = round(total_rate * assessment / 100, 0)

                crime_resp = None
                if stats.get("crime_count") is not None:
                    crime_resp = CrimeStatsResponse(
                        total_crimes=_decimal_to_num(stats["crime_count"]) or 0,
                        violent_crimes=_decimal_to_num(stats.get("violent_crimes")) or 0,
                        property_crimes=_decimal_to_num(stats.get("property_crimes")) or 0,
                        year_over_year_change_pct=_decimal_to_num(stats.get("crime_change_pct")),
                    )

                permit_resp = None
                if stats.get("permit_count") is not None:
                    permit_resp = PermitStatsResponse(
                        total_permits=_decimal_to_num(stats["permit_count"]) or 0,
                        construction_permits=_decimal_to_num(stats.get("permit_construction_count")) or 0,
                        transform_permits=_decimal_to_num(stats.get("permit_transform_count")) or 0,
                        demolition_permits=_decimal_to_num(stats.get("permit_demolition_count")) or 0,
                        total_cost=_decimal_to_num(stats.get("permit_total_cost")) or 0,
                    )

                tax_resp = None
                if res_rate is not None:
                    tax_resp = TaxRateResponse(
                        residential_rate=res_rate or 0,
                        total_tax_rate=total_rate or 0,
                        annual_tax_estimate=tax_estimate,
                    )

                return NeighbourhoodResponse(
                    borough=stats["borough"],
                    year=stats["year"],
                    crime=crime_resp,
                    permits=permit_resp,
                    tax=tax_resp,
                    safety_score=_decimal_to_num(stats.get("safety_score")),
                    gentrification_signal=stats.get("gentrification_signal"),
                )
        except Exception as e:
            logger.warning(f"DB neighbourhood lookup failed: {e}")

    # Fallback: live Montreal Open Data
    from housemktanalyzr.enrichment.montreal_data import MontrealOpenDataClient
    client = MontrealOpenDataClient()
    try:
        results = await client.get_neighbourhood_stats(borough)
        if not results:
            raise HTTPException(status_code=404, detail=f"No data found for borough: {borough}")

        stats = results[0]

        tax_estimate = None
        if stats.tax and assessment:
            tax_estimate = round(stats.tax.total_tax_rate * assessment / 100, 0)

        return NeighbourhoodResponse(
            borough=stats.borough,
            year=current_year,
            crime=CrimeStatsResponse(
                total_crimes=stats.crime.total_crimes,
                violent_crimes=stats.crime.violent_crimes,
                property_crimes=stats.crime.property_crimes,
                year_over_year_change_pct=stats.crime.year_over_year_change_pct,
            ) if stats.crime else None,
            permits=PermitStatsResponse(
                total_permits=stats.permits.total_permits,
                construction_permits=stats.permits.construction_permits,
                transform_permits=stats.permits.transform_permits,
                demolition_permits=stats.permits.demolition_permits,
                total_cost=stats.permits.total_cost,
            ) if stats.permits else None,
            tax=TaxRateResponse(
                residential_rate=stats.tax.residential_rate,
                total_tax_rate=stats.tax.total_tax_rate,
                annual_tax_estimate=tax_estimate,
            ) if stats.tax else None,
            safety_score=stats.safety_score,
            gentrification_signal=stats.gentrification_signal,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch neighbourhood data: {e}")
    finally:
        await client.close()
