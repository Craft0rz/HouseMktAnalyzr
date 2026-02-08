"""Market data fetchers for Bank of Canada and Statistics Canada.

Bank of Canada Valet API: Free, no auth, JSON/CSV/XML
 - Policy rate, mortgage rates, CPI

Statistics Canada WDS: Free, no auth, JSON/CSV
 - Unemployment by CMA, asking rents
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """A single time-series data point."""
    date: date
    value: float


@dataclass
class RateHistory:
    """Historical rate data with metadata."""
    series_id: str
    label: str
    observations: list[Observation]

    @property
    def latest(self) -> Observation | None:
        return self.observations[-1] if self.observations else None

    @property
    def previous(self) -> Observation | None:
        return self.observations[-2] if len(self.observations) >= 2 else None

    @property
    def direction(self) -> str:
        """'up', 'down', or 'stable' compared to previous observation."""
        if not self.latest or not self.previous:
            return "stable"
        diff = self.latest.value - self.previous.value
        if abs(diff) < 0.001:
            return "stable"
        return "up" if diff > 0 else "down"


# Bank of Canada Valet API series IDs
# From CHARTERED_BANK_INTEREST group:
#   V80691333 = 1-year mortgage, V80691334 = 3-year mortgage,
#   V80691335 = 5-year mortgage (conventional), V80691311 = prime rate
#   V80691336 = 5-year personal fixed term (GIC/savings — NOT mortgage)
BOC_SERIES = {
    "policy_rate": "V39079",
    "mortgage_5yr": "V80691335",
    "mortgage_3yr": "V80691334",
    "mortgage_1yr": "V80691333",
    "cpi": "V41690973",
    "prime_rate": "V80691311",
}


class BankOfCanadaClient:
    """Client for the Bank of Canada Valet API."""

    BASE = "https://www.bankofcanada.ca/valet"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_series(
        self,
        series_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RateHistory:
        """Fetch observations for a given series.

        Args:
            series_id: BoC series ID (e.g. 'V80691336')
            start_date: Start date for observations
            end_date: End date for observations

        Returns:
            RateHistory with parsed observations
        """
        client = await self._get_client()
        url = f"{self.BASE}/observations/{series_id}/json"

        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        label = ""
        series_detail = data.get("seriesDetail", {})
        if series_id in series_detail:
            label = series_detail[series_id].get("label", "")

        observations = []
        for obs in data.get("observations", []):
            obs_date = date.fromisoformat(obs["d"])
            value_str = obs.get(series_id, {}).get("v")
            if value_str is not None:
                try:
                    observations.append(Observation(
                        date=obs_date,
                        value=float(value_str),
                    ))
                except (ValueError, TypeError):
                    continue

        return RateHistory(
            series_id=series_id,
            label=label,
            observations=observations,
        )

    async def get_mortgage_rates(self, lookback_years: int = 5) -> RateHistory:
        """Get 5-year conventional mortgage rate history."""
        start = date.today() - timedelta(days=lookback_years * 365)
        return await self.get_series(BOC_SERIES["mortgage_5yr"], start_date=start)

    async def get_policy_rate(self, lookback_years: int = 5) -> RateHistory:
        """Get Bank of Canada policy (overnight) rate history."""
        start = date.today() - timedelta(days=lookback_years * 365)
        return await self.get_series(BOC_SERIES["policy_rate"], start_date=start)

    async def get_cpi(self, lookback_years: int = 5) -> RateHistory:
        """Get Consumer Price Index history."""
        start = date.today() - timedelta(days=lookback_years * 365)
        return await self.get_series(BOC_SERIES["cpi"], start_date=start)

    async def get_prime_rate(self, lookback_years: int = 5) -> RateHistory:
        """Get prime rate history."""
        start = date.today() - timedelta(days=lookback_years * 365)
        return await self.get_series(BOC_SERIES["prime_rate"], start_date=start)

    async def get_all_rates(self, lookback_years: int = 2) -> dict[str, RateHistory]:
        """Fetch all key rates in one go."""
        start = date.today() - timedelta(days=lookback_years * 365)
        results = {}
        for name, series_id in BOC_SERIES.items():
            try:
                results[name] = await self.get_series(series_id, start_date=start)
            except Exception as e:
                logger.warning(f"Failed to fetch BoC series {name} ({series_id}): {e}")
        return results


class StatCanClient:
    """Client for Statistics Canada Web Data Service."""

    # Key table IDs
    TABLES = {
        "unemployment_cma": "14-10-0096-01",
        "asking_rents": "46-10-0092-01",
        "cpi_shelter": "18-10-0004-04",
        "new_housing_price": "18-10-0205-01",
    }

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_table_metadata(self, table_id: str) -> dict:
        """Get metadata for a CANSIM table."""
        client = await self._get_client()
        pid = table_id.replace("-", "")
        url = f"https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={pid}"
        resp = await client.get(url)
        resp.raise_for_status()
        return {"url": url, "status": resp.status_code}
