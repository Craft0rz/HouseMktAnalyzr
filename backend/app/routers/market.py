"""Market intelligence API endpoints.

Serves macro-economic data (interest rates, CPI, unemployment)
fetched from Bank of Canada and Statistics Canada.
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
